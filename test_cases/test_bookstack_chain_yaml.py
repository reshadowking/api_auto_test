"""BookStack 链路 —— YAML 变量表版

与 test_bookstack_chain.py 场景相同，但链路上下文由框架的变量表承担：
用例在 YAML 里用 expect_capture 捕获 {{book_id}}，后续用例用占位符引用，
测试函数本身不碰业务字段。
"""
import uuid

import allure
import pytest

from common.assert_engine import assert_response, prepare_request
from common.bookstack_client import bookstack_client
from common.cleanup import CleanupRegistry, make_book_cleanup, report_cleanup_errors
from common.read_yaml import get_yaml_data

CASES = get_yaml_data("./datas/bookstack_chain_cases.yaml")
CASE_LIST = CASES["case_list"]
DEFAULTS = CASES.get("default_checks", {})

# 有状态链路：并行时必须落在同一个 worker
pytestmark = [pytest.mark.bookstack, pytest.mark.xdist_group(name="bookstack_chain_yaml")]


@allure.feature("BookStack 数据一致性链路（YAML 变量表）")
@allure.story("图书 CRUD 状态流转")
def test_bookstack_chain_via_yaml():
    ctx = {"suffix": uuid.uuid4().hex[:8]}   # 变量表：唯一后缀 + 后续捕获的 id/name
    registry = CleanupRegistry()

    try:
        for case in CASE_LIST:
            allure.dynamic.title(case.get("desc", case["mark"]))
            with allure.step(f"{case['mark']}：{case.get('desc', '')}"):
                # 先渲染 {{变量名}}，再发请求
                req = prepare_request(case, ctx)
                res = bookstack_client.send(
                    method=req["method"],
                    path=req["path"],
                    json=req.get("json"),
                )
                allure.attach(res.text, "响应", allure.attachment_type.TEXT)
                assert_response(res, case, defaults=DEFAULTS, variables=ctx)

            # 创建成功后立即登记清理，保证后续步骤失败也能删掉数据
            if "book_id" in ctx and not registry:
                registry.add(
                    f"删除图书 {ctx['book_id']}",
                    make_book_cleanup(bookstack_client, ctx["book_id"]),
                )
    finally:
        # 清理失败不改变用例判定，但必须上报(Allure 附件 + 控制台警告)，避免脏数据静默累积
        report_cleanup_errors(registry.run_all())
