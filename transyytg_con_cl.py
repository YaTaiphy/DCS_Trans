## python 创建虚拟环境
import os
import argparse
import json
import re
import sys
import logging

import hashlib


from util import system_prompt
from util.LLM_trans import LLM_trans_v2, dptrans
from util.extract_miz import extract_specific_file, get_files
from util.intract_miz import dictionary_intract
from util.lua_reg import isMatchLua
from util.remote_base16 import looking_translated, save_translated


parser = argparse.ArgumentParser(description="一个命令行参数")

CACHE_DIR = "./cache"
## 创建./cache目录
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# 添加保存翻译结果的函数
def save_translation_json(filename, content=None):
    with open(os.path.join(CACHE_DIR, filename), "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=4)


def get_jsonList(mizPath):
    # 获取当前路径下的json文件
    jsonList = []
    for root, dirs, files in os.walk(mizPath):
        for file in files:
            if file.endswith(".json") and not file.endswith("_translateRef.json"):
                jsonList.append(os.path.join(root, file))
    return jsonList


def readAndTranslateJson(jsonPath, api_key, onlyChs):
    count = 0
    # 读取json文件
    with open(jsonPath, "r", encoding="utf-8") as f:
        jsonData = f.read()
    # 解析json文件
    jsonData = json.loads(jsonData)

    
    # 对jsonData进行过滤，获得要翻译的jsonDataFiltered
    jsonDataFiltered = {}
    for key, value in jsonData.items():
        if "Name" in key:
            continue  # 跳过Name字段
        if "DictKey" in value:
            continue
        if isMatchLua(value):
            # 如果value是lua函数，则跳过翻译
            logging.info("value是lua函数跳过翻译：\n" + value)
            print("value是lua函数跳过翻译：\n" + value)
            continue
        if len(value) < 2:
            continue
        jsonDataFiltered[key] = value
    # 对jsonDataFiltered进行排序
    jsonDataFiltered = dict(sorted(jsonDataFiltered.items(), key=lambda item: item[0]))
    # 对jsonDataFiltered的内容计算base16，作为标识，以便查找远程、本地是否已经翻译，且可用于本地存储
    # 计算base16
    jsonDataFilteredStr = json.dumps(jsonDataFiltered, ensure_ascii=False, indent=4)
    jsonDataFilteredBase16 = hashlib.md5(jsonDataFilteredStr.encode("utf-8")).hexdigest()
    
    isRemote, remoteContent = looking_translated(jsonDataFilteredBase16)
    if isRemote:
        # 如果远程查找到了，则直接使用远程内容
        translatedJson = remoteContent
        isExistTranslatedJson = True
    else:
        # 如果远程没有查找到，则从本地缓存中查找
        print(f"远程未查找到翻译结果，尝试从本地缓存中查找: {jsonDataFilteredBase16}")
        translatedJsonPath = os.path.join(CACHE_DIR, f"{jsonDataFilteredBase16}_translated.json")
        if os.path.exists(translatedJsonPath):
            with open(translatedJsonPath, "r", encoding="utf-8") as f:
                translatedJson = json.load(f)
                isExistTranslatedJson = True
            print(f"本地缓存中查找到翻译结果: {jsonDataFilteredBase16}")
            print(f"尝试保存翻译结果到远程服务器: {jsonDataFilteredBase16}")
            save_success, save_message = save_translated(jsonDataFilteredBase16, translatedJson )
            if save_success:
                print(f"翻译结果已成功保存到远程服务器: {jsonDataFilteredBase16}")
            else:
                print(f"翻译结果保存到远程服务器失败: {save_message}")
        else:
            print(f"本地缓存中未查找到翻译结果，尝试进行翻译: {jsonDataFilteredBase16}")
            isExistTranslatedJson = False
    translate_ref = {}
    
    translated_dict = {}
    if not isExistTranslatedJson:
        test_input = "将以下英文翻译成中文，输出格式为<input_id>key</input_id><text>value</text>，其中key为DictKey_开头的键，value为翻译后的中文\n"
        for key, value in jsonDataFiltered.items():
            test_input += f"<input_id>{key}</input_id><text>{value}</text>\n"
        
        try:
            translated_output = LLM_trans_v2(system_prompt.system_prompt, test_input, api_key, CACHE_DIR=CACHE_DIR, BASE16=jsonDataFilteredBase16)
        except Exception as e:
            logging.error(f"翻译过程中出现错误: {e}")
            print(f"翻译过程中出现错误: {e}")
            exit(1)
        # 将translated_output解析为字典
        try:
            matches = re.findall(r'<input_id>(.*?)</input_id><text>(.*?)</text>', translated_output, re.DOTALL)
            for key, value in matches:
                translated_dict[key] = value.strip()
        except Exception as e:
            logging.error(f"解析翻译结果时出现错误: {e}")
            print(f"解析翻译结果时出现错误: {e}")
            exit(1)
        # 上传以及保存到本地
        print(f"尝试保存翻译结果到远程服务器: {jsonDataFilteredBase16}")
        save_success, save_message = save_translated(jsonDataFilteredBase16, translated_dict)
        if save_success:
            print(f"翻译结果已成功保存到远程服务器: {jsonDataFilteredBase16}")
        else:
            print(f"翻译结果保存到远程服务器失败: {save_message}")
        # 保存到本地
        print(f"尝试保存翻译结果到本地缓存: {jsonDataFilteredBase16}")
        with open(os.path.join(CACHE_DIR, f"{jsonDataFilteredBase16}_translated.json"), "w", encoding="utf-8") as f:
            json.dump(translated_dict, f, ensure_ascii=False, indent=4)
        print(f"翻译结果已成功保存到本地缓存: {jsonDataFilteredBase16}")
    else:
        translated_dict = translatedJson
        
    for key, value in jsonDataFiltered.items():
        # 其中跳过的键值对不进行监测，已有的键值必须在translated_dict中存在，且值不为空，否则进行记录
        if key in translated_dict and translated_dict[key]:
            translate_ref[value] = translated_dict[key]
        else:
            print(f"键 {key} 的翻译结果缺失或为空。")
        ## 写入翻译参考文件，位于jsonPath同目录下，文件名为jsonPath_translateRef.json
    with open(os.path.join(os.path.dirname(jsonPath), os.path.splitext(os.path.basename(jsonPath))[0] + "_translateRef.json"), "w", encoding="utf-8") as f:
        json.dump(translate_ref, f, ensure_ascii=False, indent=4)  # indent=4表示缩进4个空格
    
    # 在jsonData中加入翻译结果，原文本下换行然后加入翻译文本
    for key, value in jsonData.items():
        if key in translated_dict and translated_dict[key]:
            translatedText = translated_dict[key]
            if onlyChs:
                # 如果只输出中文，则不添加原文本
                if "[Script]" in key:
                    jsonData[key] = "[Script]" + translatedText
                else:
                    jsonData[key] = translatedText
            elif "Radio" in key:
                # 如果是Radio类型的文本，则不添加换行符
                jsonData[key] = "[" + value + "][" + translatedText + "]"
            elif "Script" in key:
                # 如果是Script类型的文本，则不添加换行符
                jsonData[key] = value + "[" + translatedText + "]"
            else:
                jsonData[key] = value + "\n" + translatedText

            # # 原文本下换行然后加入翻译文本
            # if onlyChs:
            #     # 如果只输出中文，则不添加原文本
            #     if "[Script]" in key:
            #         jsonData[key] = "[Script]" + translatedText
            #     else:
            #         jsonData[key] = translatedText
            # elif "Radio" in key:
            #     # 如果是Radio类型的文本，则不添加换行符
            #     jsonData[key] = "[" + value + "][" + translatedText + "]"
            # elif "Script" in key:
            #     # 如果是Script类型的文本，则不添加换行符
            #     jsonData[key] = value + "[" + translatedText + "]"
            # else:
            #     jsonData[key] = value + "\n" + translatedText
            #

    with open(jsonPath, "w", encoding="utf-8") as f:
        json.dump(jsonData, f, ensure_ascii=False, indent=4)  # indent=4表示缩进4个空格
  # 恢复print输出



## 命令行输入相关路径，以参数的形式传入
def transyytg_con(api_key, removeJson, mizPath, onlyChs):
    # mizPath = "E:/miz-translator/back/"  # 任务路径
    targetFileInZip = "l10n/DEFAULT/dictionary"
    fileList = get_files(mizPath)
    print(fileList)  # 打印文件列表

    # 遍历文件列表，解压缩文件
    for file in fileList:
        extract_specific_file(file, targetFileInZip, os.path.basename(file) + ".json", output_dir=os.path.dirname(file))

    import logging
    ## 设置日志格式

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler("./cache/log.txt", mode='a', encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logging.info("开始处理任务")
    print("开始处理任务")

    # jsonsPath = "./jsonfiles2"
    jsonsPath = mizPath
    ## 遍历json文件夹下的所有json文件
    jsonList = get_jsonList(jsonsPath)
    jsonList.sort()
    print(jsonList)  # 打印文件列表
    # try:
    #     for file in jsonList:
    #         print("处理文件")
    #         readAndTranslateJson(file, api_key, base_url, model, hint, onlyChs)
    # except Exception as e:
    #     print("处理文件时出错")
    #     ex = Exception("处理文件时出错", e)
    #     raise ex

    if(len(fileList) == 0):
        print("没有找到任务文件，请检查路径是否正确")
        ex = Exception("没有找到任务文件，请检查路径是否正确")
        raise ex

    for file in jsonList:
        try:
            print("正在处理文件:" + file)
            readAndTranslateJson(file, api_key, onlyChs)
            dictionary_intract(file)
            print("正在合并文件:" + file)
            if removeJson:
                os.remove(file)
                print("删除文件:" + file)
        except Exception as e:
            print("出错")
            ex = Exception("提交任务时出错", e)
            raise ex
    
    print("翻译完成!!!!!")

    return True

if __name__ == "__main__":
    ## 命令行输入相关路径，以参数的形式传入
    # parser.add_argument("--api_key", type=str, help="DeepL API Key")
    # parser.add_argument("--path", type=str, help="Path to the mission files")
    # ## 帮助
    # # parser.add_argument("--help", action="help", help="input --api_key and --path\nFor example: xxx.exe --api_key YOUR_API_KEY --path E:/miz-translator/back/")
    print("本软件为翻译DCS任务文件的工具，使用大模型 API进行翻译")
    intro = """
    v2.0版本最大的好处就是我为人人、人人为我，如果你有大模型API Key，那么你可以将翻译结果保存到远程服务器上，供其他人使用，如果你没有大模型API Key，那么你也可以使用其他人的翻译结果，从而节省你的翻译成本。
    v2.0版本说明如下：
    1. 增加了远程服务器查找翻译结果的功能，如果远程服务器有翻译结果，则直接使用远程结果，否则从本地缓存中查找，如果本地缓存中也没有，则进行翻译，并将翻译结果保存到远程服务器和本地缓存中。
    2. 增加了翻译结果保存到远程服务器的功能，如果翻译结果保存到远程服务器失败，则提示用户，并继续保存到本地缓存中。
    3. 增加了翻译结果保存到本地缓存的功能，如果翻译结果保存到本地缓存失败，则提示用户，并继续保存到远程服务器中。
    4. 本版本仍然为测试版本，可能存在一些问题，如果遇到问题，请联系作者。或者加QQ群 1033517336
    """
    print("作者：YATEIFEI（https://github.com/YaTaiphy/）")
    print("联系方式：l476579487@126.com")
    try:
        # 以下按照命令行进行输入
        print("当前只支持deepseek-v4-pro模型，其他模型不支持")
        print("请输出api_key：")
        api_key = input().strip()
        print("请输入翻译文件夹路径，：")
        mizPath = input().strip()
        # G:\E\miz-translator\python_dp2\python_dp\dist
        # 验证mizPath是否存在，以及文件夹内是否存在miz文件
        if not os.path.exists(mizPath):
            print("翻译文件夹路径不存在，请检查路径是否正确")
            print("按任意键退出...")
            os.system("pause")  # 只有Windows有效
            sys.exit(1)
        
        # 验证文件夹内是否存在miz文件
        miz_files = [f for f in os.listdir(mizPath) if f.endswith('.miz')]
        if not miz_files:
            print("翻译文件夹内不存在miz文件，请检查路径是否正确")
            print("按任意键退出...")
            os.system("pause")  # 只有Windows有效
            sys.exit(1)

        removeJson = False
        
        print("是否中英文混排？(y/n)：")
        onlyChs = not input().strip().lower() == 'y'
        # 对输入错误进行处理
        while onlyChs not in [True, False]:
            print("输入错误，请重新输入是否只输出中文？(y/n)：")
            onlyChs = not input().strip().lower() == 'y'
    except Exception as e:
        print("输入参数阶段错误，请检查输入是否正确")
        print("按任意键退出...")
        os.system("pause")  # 只有Windows有效
        sys.exit(1)

    # mizPath = "E:/miz-translator/back/"  # 任务路径
    targetFileInZip = "l10n/DEFAULT/dictionary"

    ## 如果mizPaths是字符串，则转换为列表
    if isinstance(mizPath, str):
        mizPaths = [mizPath]


    for mizPath in mizPaths:
        print(f"正在处理任务文件夹: {mizPath}")
        try:
            transyytg_con(api_key, removeJson, mizPath, onlyChs)
        except Exception as e:
            print(f"处理任务文件夹 {mizPath} 时出错: {e}")
            print("按任意键退出...")
            os.system("pause")
            sys.exit(1)

    print("翻译完成!!!!!")

    print("按任意键退出...")
    os.system("pause")  # 只有Windows有效
