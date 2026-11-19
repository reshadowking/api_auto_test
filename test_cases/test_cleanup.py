"""清理注册表单元测试：验证 LIFO 顺序、失败隔离、幂等"""
import pytest

from common.cleanup import CleanupRegistry

pytestmark = pytest.mark.unit


class TestCleanupRegistry:
    def test_run_in_lifo_order(self):
        """后登记的先清理（先删子资源再删父资源）"""
        order = []
        reg = CleanupRegistry()
        reg.add("first", lambda: order.append("first"))
        reg.add("second", lambda: order.append("second"))
        reg.run_all()
        assert order == ["second", "first"]

    def test_failure_does_not_block_others(self):
        """单个清理失败不影响其余清理"""
        executed = []

        def boom():
            raise RuntimeError("清理炸了")

        reg = CleanupRegistry()
        reg.add("ok1", lambda: executed.append("ok1"))
        reg.add("bad", boom)
        reg.add("ok2", lambda: executed.append("ok2"))

        errors = reg.run_all()
        assert len(errors) == 1
        assert errors[0][0] == "bad"
        assert set(executed) == {"ok1", "ok2"}

    def test_run_twice_is_safe(self):
        """重复执行不会重复清理"""
        count = []
        reg = CleanupRegistry()
        reg.add("once", lambda: count.append(1))
        reg.run_all()
        reg.run_all()
        assert len(count) == 1

    def test_len(self):
        reg = CleanupRegistry()
        assert len(reg) == 0
        reg.add("a", lambda: None)
        assert len(reg) == 1
