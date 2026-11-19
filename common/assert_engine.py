# 通用断言引擎：所有断言规则由 YAML 数据描述，用例代码零改动
import json
import re
from pathlib import Path

import allure

SCHEMA_DIR = Path(__file__).parent.parent / "schemas"

TYPE_MAP = {
    "int": int,
    "string": str,
    "str": str,
    "bool": bool,
    "float": float,
    "list": list,
    "dict": dict,
}

# 路径解析：支持 a.b、data[0].id、items[*].name 三种写法
_TOKEN_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)|\[\s*(\d+|\*)\s*\]")


def _tokens(path):
    """把 data[0].id 切成 [('key','data'), ('index','0'), ('key','id')]"""
    out = []
    for key, index in _TOKEN_RE.findall(path):
        if key:
            out.append(("key", key))
        elif index:
            out.append(("index", index))
    return out


def resolve_path(data, path):
    """按路径取值，返回 [值, ...]，[*] 通配时返回多个"""
    current = [data]
    for kind, token in _tokens(path):
        nxt = []
        for item in current:
            if kind == "key":
                if isinstance(item, dict) and token in item:
                    nxt.append(item[token])
            elif token == "*":
                if isinstance(item, list):
                    nxt.extend(item)
            else:
                if isinstance(item, list) and int(token) < len(item):
                    nxt.append(item[int(token)])
        current = nxt
    return current


def _fail(case, msg):
    raise AssertionError(f"[{case.get('mark', '?')}] {case.get('method')} {case.get('path')}：{msg}")


# ---------- 变量表：跨请求传值 ----------
# 语法：{{变量名}}，可出现在 path、json 请求体、规则 value 中
_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def render(value, variables):
    """把 {{变量名}} 替换为变量值；值本身是数字时保留类型（用于等价断言）"""
    if not variables:
        return value
    if isinstance(value, str):
        m = _VAR_RE.fullmatch(value.strip())
        if m and m.group(1) in variables:
            # 整串就是一个变量引用：返回原始对象，避免数字变成字符串
            return variables[m.group(1)]
        return _VAR_RE.sub(
            lambda x: str(variables.get(x.group(1), x.group(0))), value
        )
    if isinstance(value, dict):
        return {k: render(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, variables) for v in value]
    return value


def prepare_request(case, variables):
    """请求发出前：先把 path / params / json 里的 {{变量名}} 替换掉"""
    if not variables:
        return case
    out = dict(case)
    for key in ("path", "params", "json"):
        if key in out:
            out[key] = render(out[key], variables)
    return out


def capture(response, spec, variables, case):
    """按 expect_capture 从响应取值写入变量表：{变量名: 字段路径}"""
    if not spec:
        return
    try:
        body = response.json()
    except ValueError:
        _fail(case, "响应不是合法 JSON，无法捕获变量")
    for name, path in spec.items():
        values = resolve_path(body, path)
        if not values:
            _fail(case, f"捕获变量 {name} 失败：字段不存在 {path}")
        variables[name] = values[0]


def merge_defaults(case, defaults):
    """把全局默认校验合并进单条用例。

    规则：
      - 用例里没写的键 → 用默认值
      - 用例里写了的键 → 用例覆盖默认
      - expect_rules / expect_schema / expect_headers 这类字典/列表 → 合并（用例优先）
    """
    if not defaults:
        return case

    merged = dict(case)
    for key, default_value in defaults.items():
        if key not in merged:
            merged[key] = default_value
        elif isinstance(default_value, dict) and isinstance(merged[key], dict):
            merged[key] = {**default_value, **merged[key]}
        elif isinstance(default_value, list) and isinstance(merged[key], list):
            merged[key] = default_value + merged[key]
    return merged


def _check_type(value, type_name, where, case):
    expect = TYPE_MAP.get(type_name)
    if expect is None:
        _fail(case, f"未知类型 {type_name}（校验位置 {where}）")
    if not isinstance(value, expect) or (expect is int and isinstance(value, bool)):
        _fail(case, f"{where} 类型错误，期望 {type_name}，实际 {type(value).__name__}：{value!r}")


def _load_json_schema(name):
    """从 schemas/ 目录加载 *.json，name 可带或不带扩展名"""
    file = SCHEMA_DIR / (name if name.endswith(".json") else f"{name}.json")
    if not file.exists():
        raise AssertionError(f"JSON Schema 文件不存在：{file}")
    return json.loads(file.read_text(encoding="utf-8"))


def _validate_json_schema(body, schema_name, case):
    """用 jsonschema 校验响应结构，错误信息附带字段路径"""
    try:
        import jsonschema
    except ImportError:
        raise AssertionError("缺少依赖 jsonschema，请先 pip install jsonschema")

    schema = _load_json_schema(schema_name)
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(body), key=lambda e: list(e.absolute_path))
    if errors:
        detail = "；".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        _fail(case, f"JSON Schema[{schema_name}] 校验失败：{detail}")


def assert_response(response, case, defaults=None, variables=None):
    """按用例里的 expect_* 配置校验响应；每类校验在 Allure 中生成独立 step

    defaults：全局默认校验，用例未覆盖的部分自动补齐（见 merge_defaults）
    用例可用 expect: false 关闭全部默认校验（如 204 无响应体的接口），仅保留状态码与 JSON Schema
    variables：变量表（dict），跨请求共享。传了就支持 {{变量名}} 占位与 expect_capture
    """
    if variables is not None:
        # 占位符先替换（path/json/规则 value 都可引用），再走原有校验
        case = render(case, variables)
    case = merge_defaults(case, defaults)
    if case.get("expect") is False:
        # 免检：只保留状态码与 JSON Schema，其余默认校验全部跳过
        case = {
            k: v
            for k, v in case.items()
            if not k.startswith("expect_")
            or k in ("expect_code", "expect_json_schema")
        }
    expect_code = case.get("expect_code")
    if expect_code is not None:
        with allure.step(f"校验状态码应为 {expect_code}"):
            if response.status_code != expect_code:
                _fail(
                    case,
                    f"状态码不匹配，期望 {expect_code}，实际 {response.status_code}",
                )

    # 状态码正确后立即捕获变量：同一条用例里后续的 equals_var 能引用到本响应的字段
    if variables is not None:
        with allure.step(f"捕获变量 {list((case.get('expect_capture') or {}).keys())}"):
            capture(response, case.get("expect_capture"), variables, case)

    # 响应耗时（性能基线）
    max_time = case.get("expect_max_time")
    if max_time is not None:
        elapsed = getattr(response, "elapsed_seconds", None)
        if elapsed is None:
            elapsed = response.elapsed.total_seconds()
        with allure.step(f"校验响应耗时 ≤ {max_time}s（实际 {elapsed:.3f}s）"):
            if elapsed > max_time:
                _fail(case, f"响应耗时 {elapsed:.2f}s 超过上限 {max_time}s")

    # 响应头
    for header, expect_value in (case.get("expect_headers") or {}).items():
        actual = response.headers.get(header)
        with allure.step(f"校验响应头 {header}"):
            if actual is None:
                _fail(case, f"响应头缺失：{header}")
            if expect_value is not None and expect_value.lower() not in actual.lower():
                _fail(case, f"响应头 {header} 期望包含 {expect_value!r}，实际 {actual!r}")

    # 契约测试：校验响应是否符合 OpenAPI 文档承诺
    contract_name = case.get("expect_contract")
    if contract_name:
        with allure.step(f"按契约 [{contract_name}] 校验响应"):
            from common.contract import validate_contract

            errors = validate_contract(
                contract_name,
                case["method"],
                response.url,
                response,
                case.get("json"),
            )
            if errors:
                _fail(case, "契约校验失败：" + "；".join(errors[:3]))

    schema = case.get("expect_schema") or {}
    rules = case.get("expect_rules") or []
    json_schema = case.get("expect_json_schema")
    if not schema and not rules and not json_schema:
        return

    try:
        body = response.json()
    except ValueError:
        _fail(case, "响应不是合法 JSON，无法做字段校验")

    if json_schema:
        with allure.step(f"按 JSON Schema [{json_schema}] 校验响应结构"):
            _validate_json_schema(body, json_schema, case)

    for path, type_name in schema.items():
        with allure.step(f"校验字段 {path} 类型为 {type_name}"):
            values = resolve_path(body, path)
            if not values:
                _fail(case, f"字段不存在：{path}")
            for v in values:
                _check_type(v, type_name, path, case)

    for rule in rules:
        with allure.step(f"校验字段 {rule['field']} 满足 {rule['rule']}"):
            _apply_rule(body, rule, case)


def _apply_rule(body, rule, case):
    path = rule["field"]
    kind = rule["rule"]
    values = resolve_path(body, path)

    if kind == "not_empty":
        if not values:
            _fail(case, f"字段不存在：{path}")
        for v in values:
            if v is None or v == "" or v == [] or v == {}:
                _fail(case, f"字段为空：{path}")
    elif kind == "not_null":
        if not values:
            _fail(case, f"字段不存在：{path}")
        for v in values:
            if v is None:
                _fail(case, f"字段为 null：{path}")
    elif kind == "contains":
        for v in values:
            if rule["value"] not in str(v):
                _fail(case, f"字段 {path} 不包含 {rule['value']!r}：{v!r}")
    elif kind == "equals":
        for v in values:
            if v != rule["value"]:
                _fail(case, f"字段 {path} 期望 {rule['value']!r}，实际 {v!r}")
    elif kind == "equals_var":
        # value 在 render 阶段已被替换成变量值（保持原始类型）
        expect = rule["value"]
        for v in values:
            if v != expect:
                _fail(case, f"字段 {path} 期望等于变量值 {expect!r}，实际 {v!r}")
    elif kind == "min_length":
        for v in values:
            if len(str(v)) < rule["value"]:
                _fail(case, f"字段 {path} 长度不足 {rule['value']}：{v!r}")
    elif kind == "max_length":
        for v in values:
            if len(str(v)) > rule["value"]:
                _fail(case, f"字段 {path} 长度超过 {rule['value']}：{v!r}")
    elif kind == "between":
        low, high = rule["min"], rule["max"]
        for v in values:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                _fail(case, f"字段 {path} 不是数值，无法做范围校验：{v!r}")
            if not low <= v <= high:
                _fail(case, f"字段 {path} 超出范围 [{low}, {high}]：{v!r}")
    elif kind == "matches":
        pattern = re.compile(rule["value"])
        for v in values:
            if not pattern.search(str(v)):
                _fail(case, f"字段 {path} 不匹配正则 {rule['value']!r}：{v!r}")
    elif kind == "absent":
        if values:
            _fail(case, f"字段不应出现但存在：{path}（安全校验）")
    else:
        _fail(case, f"未知校验规则 {kind}")
