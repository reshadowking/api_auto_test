"""契约测试引擎单元测试：用假响应验证 OpenAPI 契约校验"""
import pytest

from common.contract import validate_contract

pytestmark = pytest.mark.unit

CONTRACT = "reqres_openapi"
URL = "https://reqres.in/api/users"


class FakeRequest:
    def __init__(self, headers):
        self.headers = headers


class FakeResponse:
    def __init__(self, status, body, headers=None, url=URL):
        self.status_code = status
        self.content = body if isinstance(body, bytes) else str(body).encode()
        self.headers = headers or {"Content-Type": "application/json"}
        self.url = url
        self.request = FakeRequest({"Content-Type": "application/json"})


VALID_LIST = (
    b'{"page":1,"per_page":6,"total":12,"total_pages":2,'
    b'"data":[{"id":1,"email":"a@b.com","first_name":"A","last_name":"B","avatar":"x"}],'
    b'"support":{"url":"x"}}'
)


class TestContract:
    def test_valid_response_passes(self):
        resp = FakeResponse(200, VALID_LIST)
        assert validate_contract(CONTRACT, "GET", resp.url, resp) == []

    def test_wrong_status_code_fails(self):
        """契约里 /api/users GET 只定义 200/400，返回 500 应报错"""
        resp = FakeResponse(500, b'{"error":"boom"}')
        errors = validate_contract(CONTRACT, "GET", resp.url, resp)
        assert errors, "500 不符合契约应返回错误"

    def test_missing_required_field_fails(self):
        """缺少契约要求的分页字段应报错"""
        body = b'{"page":1,"per_page":6,"total":12,"total_pages":2,"data":[]}'
        resp = FakeResponse(200, body)
        assert validate_contract(CONTRACT, "GET", resp.url, resp) == []

        body_missing = b'{"data":[]}'
        resp2 = FakeResponse(200, body_missing)
        assert validate_contract(CONTRACT, "GET", resp2.url, resp2), (
            "缺少 page/per_page 等必填字段应报错"
        )

    def test_wrong_field_type_fails(self):
        """字段类型与契约不符应报错"""
        body = b'{"page":"one","per_page":6,"total":12,"total_pages":2,"data":[]}'
        resp = FakeResponse(200, body)
        assert validate_contract(CONTRACT, "GET", resp.url, resp), (
            "page 应为整数却给字符串，应报错"
        )

    def test_unknown_contract_raises(self):
        resp = FakeResponse(200, VALID_LIST)
        with pytest.raises(AssertionError, match="契约文件不存在"):
            validate_contract("no_such_contract", "GET", resp.url, resp)
