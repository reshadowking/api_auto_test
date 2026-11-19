# 接口自动化测试框架

> 双被测对象：Reqres 公开 API（契约测试）+ BookStack 真实系统（本地 Docker，有状态链路）

## 技术栈
Python + pytest + requests + YAML + JSON Schema + OpenAPI 契约 + Allure + pytest-xdist + GitHub Actions

## 核心能力

### 1. 通用断言引擎（`common/assert_engine.py`）
断言全部由 YAML 描述，**新增接口只改数据文件，Python 代码零改动**。

| 配置项 | 说明 |
|---|---|
| `expect_code` | 期望状态码 |
| `expect_schema` | 字段路径 → 类型，支持 `a.b` / `data[0].id` / `items[*].name` |
| `expect_rules` | 业务规则：`not_empty` `not_null` `contains` `equals` `min_length` `max_length` `between` `matches` `absent` `equals_var` |
| `expect_json_schema` | 引用 `schemas/*.json`，用 JSON Schema 校验完整响应结构 |
| `expect_contract` | 引用 `contracts/*.json` 的 OpenAPI 规范做契约校验 |
| `expect_max_time` | 响应耗时上限（性能基线） |
| `expect_headers` | 响应头包含校验 |
| `expect_capture` | 从响应取值写入变量表：`{变量名: 字段路径}`，供后续请求引用 |

### 2. 默认校验（`default_checks`）
YAML 顶部的 `default_checks` 定义全局默认校验，**用例没写就用默认值，写了就覆盖**：

```yaml
default_checks:
  expect_max_time: 5
  expect_headers:
    Content-Type: application/json
  expect_rules:
    - field: password
      rule: absent
```

合并规则：标量键由用例覆盖；字典/列表合并（用例优先）；`expect: false` 关闭默认校验（用于 204 无响应体接口）。

### 2.5 变量表（跨请求传值）

把上一步响应里的值存起来，供后续请求的 `path` / `json` / 断言引用：

```yaml
- mark: create
  method: POST
  path: /api/books
  json: { name: "自动测试-{{suffix}}" }
  expect_capture:            # 状态码校验通过后捕获，写入变量表
    book_id: id
    book_name: name

- mark: get
  method: GET
  path: /api/books/{{book_id}}   # 请求前替换
  expect_rules:
    - field: id
      rule: equals_var           # 断言字段等于变量值（保持原始类型）
      value: "{{book_id}}"
```

用法：变量表由调用方创建并传入。

```python
ctx = {"suffix": "abc"}
req = prepare_request(case, ctx)          # 请求前：渲染 path/params/json
res = client.send(method=req["method"], path=req["path"], json=req.get("json"))
assert_response(res, case, variables=ctx) # 校验 + 捕获
```

- 不传 `variables` 时行为与旧版完全一致
- 变量表不做全局单例，避免 pytest-xdist 并行时跨用例污染
- 示例见 `datas/bookstack_chain_cases.yaml` 与 `test_cases/test_bookstack_chain_yaml.py`

### 3. 契约测试（`common/contract.py` + `contracts/`）
用 OpenAPI 规范校验真实响应是否符合文档承诺，与断言引擎互补：

- `assert_engine` 校验「我们期望什么」
- `contract` 校验「文档承诺了什么」（**发现文档与实现漂移**）

### 4. 测试数据清理（`common/cleanup.py`）
用例创建的数据登记到 `CleanupRegistry`，**无论成功失败都自动清理**（LIFO 顺序、失败隔离），避免数据污染造成的 flaky。

### 5. 数据一致性链路（真实系统）
`test_bookstack_chain.py` 在本地 BookStack 上验证：
**创建 → 查询验证持久化 → 更新 → 二次查询验证 → 删除 → 查询应 404 → 列表不含已删除项**

### 6. 报告由数据驱动
每个校验项自动生成独立 Allure step，名称直接来自 YAML：
```
- 校验状态码应为 200
- 校验响应耗时 ≤ 5s（实际 0.745s）
- 按契约 [reqres_openapi] 校验响应
- 按 JSON Schema [reqres_user_list] 校验响应结构
- 校验字段 data[*].email 满足 matches
- 校验字段 data[*].password 满足 absent
```

### 7. 并行执行（pytest-xdist）
无状态用例可多进程并行；**有状态链路在并行模式下自动跳过**，保证执行顺序。

### 8. 单元测试
断言引擎、契约引擎、清理注册表均有独立单元测试，用假响应验证，**不依赖网络**，秒级完成——这是框架区别于脚本的关键。

## 目录结构
```
common/     api_client.py · assert_engine.py · bookstack_client.py · contract.py · cleanup.py
contracts/  OpenAPI 契约规范
datas/      接口用例 YAML
schemas/    JSON Schema 文件
test_cases/ 用例层（零接口专属断言代码）
config/     .env（敏感信息）· env_public.yaml
```

## 运行

```bash
pip install -r requirements.txt
pytest                          # 全部（需本地 BookStack 已启动）
pytest -m "not bookstack"       # Reqres + 单元测试（CI 同款）
pytest -m bookstack             # 仅 BookStack 链路（串行）
pytest -m unit                  # 仅单元测试，不碰网络，秒级
pytest -n 4 -m "not bookstack"  # 4 进程并行
python run_main.py              # 执行并生成 Allure 报告
```

> ⚠️ Reqres 免费额度 250 次/天。额度耗尽后 YAML 用例会失败，错误信息会明确提示 `rate_limit_exceeded`；
> 此时可用 `pytest -m "unit or bookstack"` 继续验证框架能力。

## BookStack 环境

```bash
cd ../../项目三-BookStack实战/bookstack && docker compose up -d
```
首次使用需在 `config/.env` 配置 `BOOKSTACK_TOKEN_ID` / `BOOKSTACK_TOKEN_SECRET`。
（数据库端口使用 13307，因 Windows 预留了 3300–3500 段）

## CI
`.github/workflows/test.yml`：push / PR 自动执行 `pytest -m "not bookstack"` 并上传 Allure 报告。
