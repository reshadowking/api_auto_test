#请求封装类
import requests
import os
from pathlib import Path
from dotenv import load_dotenv
from common.read_yaml import get_yaml_data
from requests.exceptions import Timeout, ConnectionError, RequestException

cur_file = Path(__file__)
BASE_ROOT = cur_file.parent.parent
#加载私密账号
load_dotenv(str(BASE_ROOT / "config" / ".env"))
#加载公共域名配置
public_config = get_yaml_data(str(BASE_ROOT / "config" / "env_public.yaml"))


class ApiClient:
    def __init__(self):
        self.base_url = public_config["base_url"]
        self.timeout = public_config["request_timeout"]
        self.session = requests.Session()
        # 基础公共请求头
        self.session.headers.update(public_config["global_headers"])
        # 从.env读取Reqres专属API密钥
        self.api_key = os.getenv("REQRES_API_KEY")
        if self.api_key:
            self.session.headers["X-API-Key"] = self.api_key

        self.token = ""
    def full_url(self,path):       
        #自动处理首位斜杠
        base = self.base_url.rstrip("/")
        p = path.lstrip("/")
        return f"{base}/{p}"
    def login(self):
        email = os.getenv("LOGIN_EMAIL")
        pwd = os.getenv("LOGIN_PWD")
        print("读取到的邮箱",email)
        print("读取到的密码",pwd)
        login_url =self.full_url("/api/login")
        resp = self.session.post(login_url,json={"email":email,"password":pwd})
        print("登录接口返回",resp.text)
        try:
            body = resp.json()
        except ValueError:
            raise AssertionError(f"登录返回非 JSON（状态码 {resp.status_code}）：{resp.text[:200]}")
        if "token" not in body:
            # 常见原因：免费额度耗尽（rate_limit_exceeded）或账号密码错误
            raise AssertionError(
                f"登录失败（状态码 {resp.status_code}）：{body.get('error', body)}。"
                "若为 rate_limit_exceeded，说明 Reqres 免费额度已用完，需等待重置或改用本地接口。"
            )
        self.token = body["token"]
        self.session.headers["Authorization"]=f"Bearer {self.token}"
        return self.token

    def send(self, method, path, params=None, data=None, json=None, files=None):
        url = self.full_url(path)
        print("完整请求地址：", url)
        try:
            res = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                timeout=self.timeout
            )
        except Timeout:
            raise AssertionError(f"接口请求超时，限制{self.timeout}秒，请求地址：{url}")
        except ConnectionError:
            raise AssertionError(f"网络连接失败，无法访问地址：{url}，检查域名或网络")
        except RequestException as e:
            raise AssertionError(f"接口请求异常：{str(e)}，请求地址：{url}")
        # 把耗时挂到响应对象上，供断言引擎的 max_time 规则使用
        res.elapsed_seconds = res.elapsed.total_seconds()
        return res
    #简化send调用
    def get(self,path,params=None):
        return self.send("GET",path,params=params)
    def post(self,path,json=None):
        return self.send("POST",path,json=json)
    def put(self,path,json=None):
        return self.send("PUT",path,json=json)
    def delete(self,path,params=None):
        return self.send("DELETE",path,params=params)


    def logout(self):
        self.session.close()
        print("会话关闭，登出完成")

        
api_client = ApiClient()

