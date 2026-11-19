"""变量表单元测试：{{变量名}} 占位、expect_capture 捕获、equals_var 规则"""
import pytest

from common.assert_engine import assert_response, prepare_request, render


class FakeResponse:
    status_code = 200
    headers = {"Content-Type": "application/json"}
    request = None
    elapsed_seconds = 0.01

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def test_render_placeholder():
    assert render("/api/books/{{bid}}", {"bid": 42}) == "/api/books/42"
    assert render({"name": "{{n}}-x"}, {"n": "a"}) == {"name": "a-x"}
    assert render(["{{a}}", "{{b}}"], {"a": 1, "b": 2}) == [1, 2]


def test_render_preserves_type():
    """整串就是一个变量时保留原始类型，数字不会变成字符串"""
    assert render("{{bid}}", {"bid": 42}) == 42
    assert isinstance(render("{{bid}}", {"bid": 42}), int)


def test_render_missing_variable_keeps_placeholder():
    assert render("{{missing}}", {"other": 1}) == "{{missing}}"


def test_render_without_variables_is_noop():
    case = {"path": "/a/{{x}}"}
    assert render(case, None) == case


def test_prepare_request_only_touches_request_fields():
    case = {"method": "GET", "path": "/a/{{id}}", "json": {"n": "{{name}}"},
            "mark": "t", "expect_rules": [{"value": "{{id}}"}]}
    out = prepare_request(case, {"id": 1, "name": "x"})
    assert out["path"] == "/a/1"
    assert out["json"] == {"n": "x"}
    # 断言配置保持原样，由 assert_response 负责渲染
    assert out["expect_rules"] == [{"value": "{{id}}"}] and out["mark"] == "t"


def test_capture_writes_variables():
    ctx = {}
    case = {"mark": "c", "expect_code": 200,
            "expect_capture": {"bid": "id", "bname": "data.name"}}
    assert_response(FakeResponse({"id": 7, "data": {"name": "书"}}), case, variables=ctx)
    assert ctx == {"bid": 7, "bname": "书"}


def test_capture_missing_field_fails():
    with pytest.raises(AssertionError, match="捕获变量"):
        assert_response(FakeResponse({"id": 7}), {"mark": "c", "expect_code": 200,
                                                  "expect_capture": {"x": "nope"}}, variables={})


def test_equals_var():
    case = {"mark": "v", "expect_code": 200,
            "expect_rules": [{"field": "id", "rule": "equals_var", "value": "{{bid}}"}]}
    assert_response(FakeResponse({"id": 9}), case, variables={"bid": 9})


def test_equals_var_type_strict():
    """类型不同要失败：字符串 "9" 不等于数字 9"""
    case = {"mark": "v", "expect_code": 200,
            "expect_rules": [{"field": "id", "rule": "equals_var", "value": "{{bid}}"}]}
    with pytest.raises(AssertionError):
        assert_response(FakeResponse({"id": "9"}), case, variables={"bid": 9})


def test_no_variables_keeps_old_behavior():
    """不传 variables 时行为不变，{{...}} 原样保留也不会报错"""
    case = {"mark": "old", "expect_code": 200,
            "expect_rules": [{"field": "id", "rule": "not_null"}]}
    assert_response(FakeResponse({"id": 1}), case)


def test_capture_runs_after_status_check():
    """状态码不匹配时不捕获变量，避免把错误响应写进上下文"""
    ctx = {}
    case = {"mark": "c", "expect_code": 201, "expect_capture": {"bid": "id"}}
    with pytest.raises(AssertionError):
        assert_response(FakeResponse({"id": 7}), case, variables=ctx)
    assert ctx == {}
