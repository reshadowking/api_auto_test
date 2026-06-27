import sys
from pathlib import Path

# 获取项目根目录 newtt
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

#全局夹具，业务逻辑
import pytest
from common.read_yaml import get_yaml_data 
from common.api_client import api_client

#读取所有测试用例

all_case = get_yaml_data("./datas/all_api_cases.yaml")["case_list"]
# 打印调试
print("all_case 类型：", type(all_case))
print("all_case 内容：", all_case)
#参数化夹具，循环所有用例，动态绑定mark标签
@pytest.fixture(params = all_case, scope="function")
def case_info(request):
    case =request.param
    tag = case["mark"]
    request.node.add_marker(getattr(pytest.mark,tag))
    yield case

#session全局前置登录：整个项目执行前只登陆一次
@pytest.fixture(scope="session",autouse =True)
def before_all_login():
   api_client.login()
   yield
   api_client.logout()
