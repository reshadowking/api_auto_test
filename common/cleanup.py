# 测试数据清理：用例创建的数据登记后自动清理，避免污染环境导致后续用例 flaky
import logging

logger = logging.getLogger(__name__)


class CleanupRegistry:
    """按 LIFO（后进先出）顺序执行清理动作，保证依赖关系正确

    用法：
        cleanup.add("删除图书 12", lambda: client.delete("/api/books/12"))
        cleanup.run_all()   # 用例结束后调用
    """

    def __init__(self):
        self._tasks = []

    def add(self, description, fn):
        self._tasks.append((description, fn))
        return fn

    def run_all(self):
        """执行全部清理；单个失败不影响其余清理继续执行"""
        errors = []
        while self._tasks:
            description, fn = self._tasks.pop()
            try:
                fn()
                logger.info("清理成功：%s", description)
            except Exception as e:  # noqa: BLE001 - 清理失败不能中断其他清理
                logger.warning("清理失败：%s -> %s", description, e)
                errors.append((description, e))
        return errors

    def __len__(self):
        return len(self._tasks)


def make_book_cleanup(client, book_id):
    """BookStack 专用清理动作：删除图书（不存在时忽略）"""

    def _delete():
        res = client.delete(f"/api/books/{book_id}")
        # 204 = 删除成功，404 = 已被用例自己删掉，都视为清理完成
        if res.status_code not in (204, 404):
            raise AssertionError(f"清理图书 {book_id} 失败，状态码 {res.status_code}")

    return _delete


def report_cleanup_errors(errors):
    """上报清理失败清单：写 Allure 附件 + 控制台警告

    清理失败不改变用例判定（用例结果仍由断言决定），但必须让团队看见
    「环境可能有残留」，避免脏数据静默累积导致后续用例 flaky。
    用法：report_cleanup_errors(registry.run_all())
    """
    if not errors:
        return
    detail = "；".join(f"{desc}: {err}" for desc, err in errors)
    try:
        import allure

        allure.attach(detail, "清理失败(环境可能有残留)", allure.attachment_type.TEXT)
    except Exception:  # noqa: BLE001 - 上报失败不能影响测试收尾
        pass
    print(f"[警告] 清理失败 {len(errors)} 项，环境可能有残留：{detail}")
