import pytest
import subprocess

if __name__ == "__main__":
    #执行全部用例
    pytest.main(["test_cases/",
                 "-s",
                 "-v",
                 "--alluredir=report_raw",
                 "--clean-alluredir"
                 ])
    
    #生成allure网页报告
    subprocess.call("allure generate report_raw -o allure_html --clean",shell=True)
    print("\n测试执行完毕，正在启动Allure报告服务，按 Ctrl+C 正常关闭服务\n")
    try:     
        #打开报告
        subprocess.call("allure open allure_html",shell=True)
    except KeyboardInterrupt:
        # 捕获Ctrl+C中断，打印友好提示，不抛出红色异常栈
        print("\n✅ Allure服务已正常关闭，程序退出")