#读取yaml通用函数
import yaml
def get_yaml_data(file_path):
    with open(file_path,"r",encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data
