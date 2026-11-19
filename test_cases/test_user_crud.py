import allure
from common.api_client import api_client
from common.assert_engine import assert_response


@allure.feature("用户模块")
def test_all_user_api(case_info, before_all_login):
    method = case_info["method"]
    path = case_info["path"]
    params = case_info.get("params")
    body = case_info.get("json")
    case_desc = case_info.get("desc", f"{method} {path}")

    allure.dynamic.title(case_desc)
    allure.dynamic.story(case_info.get("mark", "未分类"))

    with allure.step("1. 发起接口请求"):
        response = api_client.send(method=method, path=path, params=params, json=body)
        allure.attach(response.text, "完整接口返回数据", allure.attachment_type.TEXT)

    with allure.step("2. 按用例配置校验响应"):
        assert_response(response, case_info)
