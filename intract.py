import os
import json
from pathlib import Path
import shutil
import zipfile

def read_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

def escape_to_lua_string(s):
    """将 Python 字符串转义为 Lua 风格的字符串"""
    s = s.replace('\\', '\\\\')  # 先替换 \ → \\
    s = s.replace('"', '\\"')    # 替换 " → \"
    s = s.replace('\n', '\\\n')   # 替换 \n → \\n
    return s

def dict_to_lua_a_table(py_dict):
    """将 Python 字典转换为 Lua 表字符串"""
    lua_entries = []
    for key, value in py_dict.items():
        escaped_value = escape_to_lua_string(str(value))
        lua_entry = f'\t["{key}"] = "{escaped_value}",'
        lua_entries.append(lua_entry)
    lua_str = "{\n" + "\n".join(lua_entries) + "\n}"
    return lua_str

### 追加现有zip包内的文件
def process_lua_to_zip(lua_str, target_zip_path, internal_zip_path):
    """
    将Lua字符串写入临时文件，追加到ZIP包指定路径，并清理临时文件
    
    :param lua_str: Lua表字符串内容
    :param target_zip_path: 目标ZIP文件绝对路径（如：/data/archive.zip）
    :param internal_zip_path: ZIP内存储路径（如：/l10n/CN/dictionary）
    """
    # 创建临时工作目录
    temp_dir = Path("temp_lua_build")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # 定义临时文件路径
        temp_file = temp_dir / "dictionary"
        
        # 1. 写入临时文件
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(lua_str)
        
        # 2. 处理目标ZIP路径
        target_zip = Path(target_zip_path)
        target_zip.parent.mkdir(parents=True, exist_ok=True)
        
        # 3. 处理ZIP内路径
        internal_path = Path(internal_zip_path).relative_to('/')  # 移除开头的/
        zip_internal_path = str(internal_path / "dictionary")
        
        # 4. 追加到ZIP文件
        with zipfile.ZipFile(target_zip, 'a', zipfile.ZIP_DEFLATED) as zipf:
            # 删除已存在的旧文件（如果存在）
            if zip_internal_path in zipf.namelist():
                zipf.remove(zip_internal_path)
                print(f"已删除旧文件：{zip_internal_path}")
            zipf.write(temp_file, arcname=zip_internal_path)
        
        print(f"成功更新ZIP文件：{target_zip}")
        print(f"ZIP内存储路径：{zip_internal_path}")
        
    finally:
        # 5. 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)

def dictionary_intract(jsonPath):
    dic_data = read_json_file(jsonPath)
    
    dic_str = "dictionary = \n"
    dic_str = dic_str + dict_to_lua_a_table(dic_data)
    dic_str = dic_str + " -- end of dictionary\n"
    
    ## 将翻译后的json数据写入文件
    ## dic_str写入名为dictionary无后缀的文件，存入同文件夹下同名zip包内，路径为/l10n/CN/dictionary
    process_lua_to_zip(
        lua_str=dic_str,
        target_zip_path= os.path.splitext(jsonPath)[0],  # 目标ZIP文件路径
        internal_zip_path="/l10n/CN"  # ZIP内存储路径
    )
    
    
if __name__ == "__main__":
    jsonPath = "E:\Eagle Dynamics\DCS World\Mods\campaigns\FA-18C Flaming Sunrise\STAGE 2 80 perf.miz.json"  # 任务路径 
    isOK = dictionary_intract(jsonPath)