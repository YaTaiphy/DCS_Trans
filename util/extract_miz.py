import re
import zipfile
import os
import json

from . import intract_miz

mizPath = "G:\\E\\FROG-7"  # 任务路径

targetFileInZip = "l10n/DEFAULT/dictionary"

## 遍历文件夹，提取文件
def get_files(mizPath):
    # 获取当前路径下的文件
    fileList = []
    for root, dirs, files in os.walk(mizPath):
        for file in files:
            if file.endswith(".miz"):
                fileList.append(os.path.join(root, file))
    return fileList

## 解压缩文件
import zipfile
import os


def extract_and_rename(zip_path, target_file, new_name, output_dir='.'):
    """
    从ZIP中提取特定文件并重命名

    :param zip_path: ZIP文件路径
    :param target_file: ZIP中要提取的文件名
    :param new_name: 重命名后的文件名
    :param output_dir: 输出目录(默认为当前目录)
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 提取并重命名
        with zip_ref.open(target_file) as file_in_zip:
            with open(os.path.join(output_dir, new_name), 'wb') as file_out:
                file_out.write(file_in_zip.read())
                print(f"Extracted and renamed {target_file} to {new_name} in {output_dir}.")


def find_dictkey_entries(input_string):
    pattern = r'\["DictKey_\w+"\]\s*=\s*'
    matches = re.finditer(pattern, input_string, re.DOTALL)

    startEnd = [(match.start(), match.end()) for match in matches]

    entries = {}

    for i in range(len(startEnd)):
        key_start = startEnd[i][0]
        key_end = startEnd[i][1]
        if i != len(startEnd) - 1:
            value_start = startEnd[i][1]
            value_end = startEnd[i + 1][0] - 1
        else:
            value_start = startEnd[i][1] + 1
            value_end = len(input_string) - 1
        key = input_string[key_start:key_end].rstrip(' =').lstrip('[').rstrip(']').strip('"')
        value = input_string[value_start:value_end].strip('\n \t').rstrip(',').strip('"')
        entries[key] = value
    return entries


# 精确路径匹配提取
def extract_specific_file(zip_path, target_path, new_name=None, output_dir='.'):
    """
    从ZIP中提取特定路径下的文件（可处理重名文件）

    :param zip_path: ZIP文件路径
    :param target_path: ZIP中文件的完整路径(如 'folder/subfolder/file.txt')
    :param new_name: 重命名后的文件名(可选)
    :param output_dir: 输出目录
    :return: 提取的文件路径
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # 标准化路径比较（确保路径分隔符一致）
        target_path = target_path.replace('\\', '/')

        # 查找完全匹配的文件
        matched_files = [f for f in zip_ref.namelist()
                         if f.replace('\\', '/') == target_path]

        if not matched_files:
            raise FileNotFoundError(f"未找到路径 '{target_path}' 下的文件")

        # 如果未指定新名称，则使用原文件名
        if new_name is None:
            new_name = os.path.basename(target_path)

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, new_name)

        with zip_ref.open(matched_files[0]) as file_in_zip, \
                open(output_path, 'w', encoding='utf-8') as file_out:

            dic_str = file_in_zip.read().decode('utf-8').replace('\\"', '"').replace('\\\n', '\n').replace('\\\\', '\\')
            dic_str = re.search(r'\{([\s\S]*)\}', dic_str).group(0)
            # pattern = r'\["(DictKey_\w+)"\]\s*=\s*"([\s\S]*?)"(?=,\n)'
            # 使用正则表达式提取键值对
            # pattern = r'\["(DictKey[\w_]+)"\]\s*=\s*"((?:\\"|[^"])*)"'
            # matches = re.findall(pattern, dic_str, re.DOTALL)
            # result = {}
            # for key, value in matches:
            #     # 处理转义字符：\" → ", \\n → \n
            #     processed_value = (
            #         value
            #     )
            #     result[key] = processed_value
            # result_temp = json.dumps(result, indent=4, ensure_ascii=False)

            result = {}
            result = find_dictkey_entries(dic_str)
            json.dump(result, file_out, indent=4, ensure_ascii=False)

        return output_path


if __name__ == "__main__":
    # 获取当前路径下的文件
    fileList = get_files(mizPath)
    print(fileList)  # 打印文件列表

    # 遍历文件列表，解压缩文件
    for file in fileList:
        extract_specific_file(file, targetFileInZip, os.path.basename(file) + ".json", output_dir=os.path.dirname(file))

        intract_miz.dictionary_intract(file + ".json")