"""断言引擎单元测试：不依赖网络，直接构造假响应验证每条规则"""
import pytest

from common.assert_engine import assert_response, merge_defaults, resolve_path

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None, elapsed=0.1):
        self.status_code = status
        self._body = body
        self.headers = headers or {"Content-Type": "application/json"}
        self.elapsed_seconds = elapsed

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def case(**kw):
    base = {"mark": "ut", "method": "GET", "path": "/fake", "expect_code": 200}
    base.update(kw)
    return base


class TestMergeDefaults:
    def test_fill_missing_key(self):
        merged = merge_defaults({"path": "/a"}, {"expect_max_time": 5})
        assert merged["expect_max_time"] == 5

    def test_case_overrides_default(self):
        merged = merge_defaults({"expect_max_time": 1}, {"expect_max_time": 5})
        assert merged["expect_max_time"] == 1

    def test_dict_merged(self):
        merged = merge_defaults(
            {"expect_headers": {"X-A": "1"}},
            {"expect_headers": {"Content-Type": "json"}},
        )
        assert merged["expect_headers"] == {"Content-Type": "json", "X-A": "1"}

    def test_list_merged_case_first(self):
        merged = merge_defaults(
            {"expect_rules": [{"field": "b", "rule": "not_null"}]},
            {"expect_rules": [{"field": "a", "rule": "absent"}]},
        )
        fields = [r["field"] for r in merged["expect_rules"]]
        assert fields == ["a", "b"]

    def test_no_defaults_returns_same(self):
        case = {"path": "/a"}
        assert merge_defaults(case, {}) == case

    def test_original_not_mutated(self):
        case = {"path": "/a"}
        merge_defaults(case, {"expect_max_time": 5})
        assert "expect_max_time" not in case


class TestExpectFalse:
    def test_expect_false_skips_default_checks(self):
        """expect: false 时只校验状态码，默认(合并进来的) header 校验不执行"""
        resp = FakeResponse(status=204, body=None, headers={})
        assert_response(
            resp,
            case(expect_code=204, expect=False),
            defaults={"expect_headers": {"Content-Type": "json"}},
        )

    def test_expect_false_keeps_explicit_checks(self):
        """expect: false 只剥默认校验，用例显式写的断言仍然执行"""
        with pytest.raises(AssertionError, match="期望 10"):
            assert_response(
                FakeResponse(body={"total": "10"}),
                case(expect=False, expect_rules=[
                    {"field": "total", "rule": "equals", "value": 10}]),
            )

    def test_defaults_applied_through_assert_response(self):
        """默认 max_time 生效：超过上限应失败"""
        with pytest.raises(AssertionError, match="响应耗时"):
            assert_response(
                FakeResponse(elapsed=9.0),
                case(),
                defaults={"expect_max_time": 1},
            )


class TestResolvePath:
    def test_nested_key(self):
        assert resolve_path({"a": {"b": 1}}, "a.b") == [1]

    def test_index(self):
        assert resolve_path({"data": [{"id": 7}, {"id": 8}]}, "data[0].id") == [7]

    def test_wildcard(self):
        assert resolve_path({"data": [{"id": 1}, {"id": 2}]}, "data[*].id") == [1, 2]

    def test_missing(self):
        assert resolve_path({"a": {}}, "a.b") == []


class TestRules:
    def test_equals_pass(self):
        assert_response(FakeResponse(body={"id": 1}), case(expect_rules=[
            {"field": "id", "rule": "equals", "value": 1}]))

    def test_equals_fail(self):
        with pytest.raises(AssertionError, match="期望 2"):
            assert_response(FakeResponse(body={"id": 1}), case(expect_rules=[
                {"field": "id", "rule": "equals", "value": 2}]))

    def test_between_pass(self):
        assert_response(FakeResponse(body={"page": 3}), case(expect_rules=[
            {"field": "page", "rule": "between", "min": 1, "max": 5}]))

    def test_between_fail(self):
        with pytest.raises(AssertionError, match="超出范围"):
            assert_response(FakeResponse(body={"page": 9}), case(expect_rules=[
                {"field": "page", "rule": "between", "min": 1, "max": 5}]))

    def test_absent_pass(self):
        assert_response(FakeResponse(body={"name": "x"}), case(expect_rules=[
            {"field": "password", "rule": "absent"}]))

    def test_absent_fail(self):
        with pytest.raises(AssertionError, match="不应出现"):
            assert_response(FakeResponse(body={"password": "x"}), case(expect_rules=[
                {"field": "password", "rule": "absent"}]))

    def test_matches_pass(self):
        assert_response(FakeResponse(body={"email": "a@b.com"}), case(expect_rules=[
            {"field": "email", "rule": "matches", "value": r"^[^@]+@[^@]+\.[^@]+$"}]))

    def test_matches_fail(self):
        with pytest.raises(AssertionError, match="不匹配正则"):
            assert_response(FakeResponse(body={"email": "not-an-email"}), case(expect_rules=[
                {"field": "email", "rule": "matches", "value": r"^[^@]+@[^@]+\.[^@]+$"}]))

    def test_max_length(self):
        with pytest.raises(AssertionError, match="长度超过"):
            assert_response(FakeResponse(body={"n": "abcdef"}), case(expect_rules=[
                {"field": "n", "rule": "max_length", "value": 3}]))

    def test_not_empty(self):
        with pytest.raises(AssertionError, match="字段为空"):
            assert_response(FakeResponse(body={"data": []}), case(expect_rules=[
                {"field": "data", "rule": "not_empty"}]))


class TestExpectations:
    def test_status_code_fail(self):
        with pytest.raises(AssertionError, match="状态码不匹配"):
            assert_response(FakeResponse(status=500), case(expect_code=200))

    def test_max_time_fail(self):
        with pytest.raises(AssertionError, match="响应耗时"):
            assert_response(FakeResponse(elapsed=3.0), case(expect_max_time=1))

    def test_header_fail(self):
        with pytest.raises(AssertionError, match="响应头缺失"):
            assert_response(FakeResponse(), case(expect_headers={"X-Token": None}))

    def test_schema_type_mismatch(self):
        with pytest.raises(AssertionError, match="类型错误"):
            assert_response(FakeResponse(body={"id": "1"}), case(
                expect_schema={"id": "int"}))

    def test_json_schema_pass(self):
        body = {"page": 1, "per_page": 6, "total": 12, "total_pages": 2,
                "data": [{"id": 1, "email": "a@b.com", "first_name": "A",
                          "last_name": "B", "avatar": "x"}]}
        assert_response(FakeResponse(body=body), case(
            expect_json_schema="reqres_user_list"))

    def test_json_schema_fail(self):
        body = {"page": "not-a-number", "per_page": 6, "total": 12,
                "total_pages": 2, "data": []}
        with pytest.raises(AssertionError, match="JSON Schema"):
            assert_response(FakeResponse(body=body), case(
                expect_json_schema="reqres_user_list"))
