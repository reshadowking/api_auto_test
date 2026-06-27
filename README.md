# 用户CRUD接口自动化测试框架
1、技术栈：Python+pytest+requests+yaml+allure
2、功能：
- 会话复用，全局登录Bearer Token鉴权
- 敏感配置分离，.env存放账号密码
- yaml数据驱动，支持自定义用例标签执行
- 多维度接口断言，预留400/404异常校验
- 一键执行脚本，自动生成allure可视化报告
3、运行方式
pip install -r requirements.txt
python run_main.py