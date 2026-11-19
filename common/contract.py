# 契约测试引擎：用 OpenAPI 规范校验真实请求/响应是否符合契约
# 与 assert_engine 的区别：assert_engine 校验"我们期望什么"，本模块校验"文档承诺了什么"
from pathlib import Path
from urllib.parse import urlparse

from openapi_core import Config, OpenAPI
from openapi_core.protocols import Request as ORequest
from openapi_core.protocols import Response as OResponse

CONTRACT_DIR = Path(__file__).parent.parent / "contracts"

_cache = {}


def load_contract(name):
    """加载 contracts/ 下的 OpenAPI 规范（缓存，避免每条用例重复解析）"""
    if name not in _cache:
        file = CONTRACT_DIR / (name if name.endswith(".json") else f"{name}.json")
        if not file.exists():
            raise AssertionError(f"契约文件不存在：{file}")
        # 关闭规范自检：第三方规范常有内部引用问题，但不影响按路径校验响应
        config = Config(spec_validator_cls=None)
        _cache[name] = OpenAPI.from_file_path(str(file), config=config)
    return _cache[name]


class SimpleRequest(ORequest):
    def __init__(self, method, url, headers, body):
        self._method = method.lower()  # 协议要求小写
        self._url = urlparse(url)
        self._headers = headers or {}
        self._body = body
        from openapi_core.datatypes import Parameters

        # path 需要可写：openapi-core 解析路由时会回填路径参数
        self.parameters = Parameters(path={}, query={}, header={}, cookie={})

    @property
    def host_url(self):
        return f"{self._url.scheme}://{self._url.netloc}"

    @property
    def path(self):
        return self._url.path

    @property
    def full_url_pattern(self):
        return f"{self.host_url}{self._url.path}"

    @property
    def method(self):
        return self._method

    @property
    def body(self):
        return self._body

    @property
    def content_type(self):
        return self._headers.get("Content-Type", "application/json")

    @property
    def mimetype(self):
        return self.content_type.split(";")[0].strip()


class SimpleResponse(OResponse):
    def __init__(self, status_code, headers, body):
        self._status_code = status_code
        self._headers = headers or {}
        self._body = body

    @property
    def status_code(self):
        return self._status_code

    @property
    def headers(self):
        return self._headers

    @property
    def data(self):
        # 协议要求响应体通过 data 暴露
        return self._body

    @property
    def content_type(self):
        return self._headers.get("Content-Type", "application/json")

    @property
    def mimetype(self):
        return self.content_type.split(";")[0].strip()


def _to_text(body):
    if body is None:
        return b""
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    import json as _json

    return _json.dumps(body, ensure_ascii=False).encode("utf-8")


def validate_contract(contract_name, method, url, response, request_body=None):
    """用契约校验一个真实响应，返回错误列表（空列表 = 符合契约）"""
    contract = load_contract(contract_name)
    req = SimpleRequest(method, url, dict(response.request.headers) if response.request else {},
                        _to_text(request_body))
    resp = SimpleResponse(response.status_code, dict(response.headers),
                          _to_text(response.content))

    try:
        contract.validate_response(req, resp)
    except Exception as e:  # noqa: BLE001 - openapi-core 用多种异常类型
        return [str(e)]
    return []
