# BookStack 真实系统客户端：Token 鉴权 + 复用 ApiClient 的请求/异常处理
import os

from dotenv import load_dotenv
from requests.exceptions import ConnectionError, RequestException, Timeout

from common.api_client import BASE_ROOT, ApiClient

load_dotenv(str(BASE_ROOT / "config" / ".env"))


class BookStackClient(ApiClient):
    """BookStack API：Authorization: Token {id}:{secret}"""

    def __init__(self):
        self.base_url = os.getenv("BOOKSTACK_BASE_URL", "http://localhost:8085")
        self.timeout = 15
        import requests

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": (
                    f"Token {os.getenv('BOOKSTACK_TOKEN_ID')}:"
                    f"{os.getenv('BOOKSTACK_TOKEN_SECRET')}"
                ),
            }
        )
        self.token = ""

    def login(self):
        """BookStack 用 Token 鉴权，无需登录流程；保留接口以兼容 fixture"""
        return None

    def logout(self):
        self.session.close()

    def send(self, method, path, params=None, data=None, json=None, files=None):
        url = self.full_url(path)
        try:
            res = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                timeout=self.timeout,
            )
        except Timeout:
            raise AssertionError(f"BookStack 请求超时（{self.timeout}s）：{url}")
        except ConnectionError:
            raise AssertionError(f"BookStack 无法连接，请确认 docker compose 已启动：{url}")
        except RequestException as e:
            raise AssertionError(f"BookStack 请求异常：{e}，地址：{url}")
        res.elapsed_seconds = res.elapsed.total_seconds()
        return res


bookstack_client = BookStackClient()
