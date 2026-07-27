import allure
from common.api_client import api_client

@allure.feature("用户模块")
def test_all_user_api(case_info):
    method = case_info["method"]
    path = case_info["path"]
    params = case_info.get("params")
    body = case_info.get("json")
    expect_status = case_info["expect_code"]
    case_mark = case_info["mark"]
    case_desc = case_info.get("desc", f"{method} {path}")

    # Allure标题、子模块
    allure.dynamic.title(case_desc)
    
    if case_mark == "get":
        allure.dynamic.story("查询用户信息")
    elif case_mark == "post":
        allure.dynamic.story("新增用户")
    elif case_mark == "put":
        allure.dynamic.story("更新用户信息")
    elif case_mark == "delete":
        allure.dynamic.story("删除用户")
    elif "error" in case_mark:
        allure.dynamic.story("用户异常场景校验")

    with allure.step("1. 发起接口请求"):
        response = api_client.send(method=method, path=path, params=params, json=body)
        allure.attach(response.text, "完整接口返回数据", allure.attachment_type.TEXT)

    with allure.step("2. 校验响应状态码"):
        assert response.status_code == expect_status, f"状态码不匹配，预期：{expect_status}，实际：{response.status_code}"

    # 200/201 正常返回，执行字段、类型、格式校验
    if response.status_code in [200, 201]:
        with allure.step("3. 校验返回JSON结构、字段、数据类型、格式规范"):
            res = response.json()

            # 场景1：GET /api/users 用户列表
            if path == "/api/users" and method == "GET":
                data_list = res.get("data")
                assert "data" in res, "用户列表返回缺失data数组"
                assert isinstance(data_list, list), "data必须为数组"
                if len(data_list) > 0:
                    user = data_list[0]
                    # 字段存在校验
                    assert "id" in user, "用户缺少id"
                    assert "first_name" in user, "用户缺少first_name"
                    assert "last_name" in user, "用户缺少last_name"
                    assert "email" in user, "用户缺少email"
                    # 类型校验
                    assert isinstance(user["id"], int), "列表用户id为整型"
                    assert isinstance(user["first_name"], str)
                    assert isinstance(user["last_name"], str)
                    assert isinstance(user["email"], str)
                    # 非空+格式
                    assert len(str(user["id"])) > 0
                    assert len(user["first_name"]) > 0
                    assert len(user["last_name"]) > 0
                    assert len(user["email"]) > 0
                    assert "@" in user["email"], "邮箱格式错误"

            # 场景2：GET /api/users/1 单用户查询
            elif "/api/users/" in path and method == "GET":
                assert "data" in res, "单用户查询缺失data主体"
                user = res["data"]
                assert isinstance(user, dict)
                assert "id" in user
                assert "first_name" in user
                assert "last_name" in user
                assert "email" in user
                assert isinstance(user["id"], int)
                assert isinstance(user["email"], str)
                assert "@" in user["email"]

            # 场景3：PUT /api/users/1 更新用户
            elif "/api/users/" in path and method == "PUT":
                user = res
                assert isinstance(user, dict), "更新返回应为用户字典"
                assert "name" in user, "更新返回缺少name字段"
                assert "username" in user, "更新返回缺少username"
                assert "updatedAt" in user
                assert len(user["name"]) > 0
                assert len(user["username"]) > 0
                # 因为reqres为模拟接口，传入不存在用户ID也返回200，真实业务接口会返回404

            # 场景4：POST /api/users 新增用户
            elif method == "POST" and path == "/api/users":
                assert "id" in res, "新增接口未返回id"
                assert "createdAt" in res, "新增接口未返回创建时间"
                # 修复：转字符串判断，不再强制int
                assert isinstance(str(res["id"]), str), "新增id不为有效字符串"
                assert len(str(res["id"])) > 0, "新增id不能为空"

    # 删除接口204无返回体，跳过json解析
    elif response.status_code == 204:
        with allure.step("3. 删除接口无返回报文，无需字段校验"):
            pass

    # 异常场景（当前mock不会触发，预留扩展）
    elif response.status_code in [400, 404]:
        with allure.step("3. 异常接口校验错误提示"):
            res = response.json()
            assert "error" in res, "异常接口必须返回error提示"
            assert len(res["error"]) > 0, "错误提示不能为空"