import sys
from pathlib import Path

# 获取项目根目录 newtt
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# 全局夹具，业务逻辑
import pytest
from common.api_client import api_client
from common.read_yaml import get_yaml_data

CASES_FILE = "./datas/all_api_cases.yaml"
_cases_yaml = get_yaml_data(CASES_FILE)

# 读取所有测试用例
all_case = _cases_yaml["case_list"]

# 全局默认校验：用例没写就用这里的，写了就覆盖（见 assert_engine.merge_defaults）
default_checks = _cases_yaml.get("default_checks", {})


def _with_defaults(case):
    """收集阶段把默认校验合并进每条用例，执行时无需再处理"""
    from common.assert_engine import merge_defaults

    return merge_defaults(case, default_checks)


# 把每条用例包成 pytest.param 并在收集阶段挂上对应 mark 标签，
# 这样 pytest -m 才能在执行前按标签筛选（运行时 add_marker 来不及生效）
def _to_params(case_list):
    params = []
    for case in case_list:
        tag = case["mark"]
        params.append(pytest.param(_with_defaults(case), marks=getattr(pytest.mark, tag)))
    return params


# 参数化夹具，循环所有用例，动态绑定 mark 标签
@pytest.fixture(params=_to_params(all_case), scope="function")
def case_info(request):
    yield request.param


# session 全局前置登录：只被需要真实接口的用例依赖，单元测试不触发
@pytest.fixture(scope="session")
def before_all_login():
    api_client.login()
    yield
    api_client.logout()


def _is_parallel(config):
    """判断是否在 xdist 并行模式（-n 参数存在）"""
    try:
        return config.getoption("numprocesses", default=None) is not None
    except (ValueError, AttributeError):
        return False


def pytest_collection_modifyitems(config, items):
    """并行执行时跳过大状态链路。

    BookStack 链路依赖「创建 → 查询 → 删除」的执行顺序和共享上下文，
    xdist 无法保证同一 class 的用例落在同一 worker，因此并行模式下直接跳过，
    由串行命令单独执行（pytest -m bookstack）。
    """
    if not _is_parallel(config):
        return
    skip = pytest.mark.skip(reason="有状态链路在并行模式下跳过，请串行执行 pytest -m bookstack")
    for item in items:
        if item.get_closest_marker("bookstack"):
            item.add_marker(skip)
