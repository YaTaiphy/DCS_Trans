## python 创建虚拟环境
import logging
import os
import argparse
import json
import threading
import sys

from deepseek import dptrans
from extract import extract_specific_file, get_files
import intract
import multiprocessing

from lua_reg import isMatchLua
def foo():
    multiprocessing.freeze_support()
# Create a lock for the shared dictionary
translation_lock = threading.Lock()

parser = argparse.ArgumentParser(description="一个命令行参数")


## 创建./cache目录
if not os.path.exists("./cache"):
    os.makedirs("./cache")

# 添加保存翻译结果的函数
def save_translation_json():
    with open("./cache/translated.json", "w", encoding="utf-8") as f:
        json.dump(translatedJson, f, ensure_ascii=False, indent=4)

def check_translation_exists(value_to_check):
    """通过遍历key值检查是否已有翻译"""
    for key in translatedJson.keys():
        if key == value_to_check:
            return True
    return False
     
### 创建已翻译文段的json文件，如果存在则读取，不存在则创建空字典
try:
    with open("./cache/translated.json", "r", encoding="utf-8") as f:
        translatedJson = json.load(f)
except FileNotFoundError:
    # 如果文件不存在，创建一个空字典
    translatedJson = {}
    # 创建空的翻译文件
    with open("./cache/translated.json", "w", encoding="utf-8") as f:
        json.dump(translatedJson, f, ensure_ascii=False, indent=4)
    



def get_jsonList(mizPath):
    # 获取当前路径下的json文件
    jsonList = []
    for root, dirs, files in os.walk(mizPath):
        for file in files:
            if file.endswith(".json"):
                jsonList.append(os.path.join(root, file))
    return jsonList

def readAndTranslateJson(jsonPath, api_key, base_url, model, hint, onlyChs):
    print("处理文件——" + jsonPath)
    count = 0
    # 读取json文件
    with open(jsonPath, "r", encoding="utf-8") as f:
        jsonData = f.read()
    # 解析json文件
    jsonData = json.loads(jsonData)
    # 按顺序遍历json文件中的文本以及key
    for key, value in jsonData.items():
        count += 1
        # 打印翻译进度
        if count % 10 == 0:
            logging.info(f"翻译进度：{count}/{len(jsonData)} of {jsonPath}")
            # print(f"翻译进度：{count}/{len(jsonData)} of {jsonPath}")
        if "Name" in key:
            continue  # 跳过Name字段
        if "DictKey" in value:
            continue
        if isMatchLua(value):
            # 如果value是lua函数，则跳过翻译
            # print("value是lua函数跳过翻译：\n"+ value)
            logging.info(f"跳过翻译：{value}")
            translatedJson[value] = ""
            continue
        if len(value) < 2:
            continue
        # 处理文本
        if isinstance(value, str):
            ## 判断是否已经翻译过，translatedJson为字典，key为原文本，value为翻译后的文本
            if check_translation_exists(value) and translatedJson[value] != "":
                # 如果已经翻译过，则直接使用翻译后的文本
                translatedText = translatedJson[value]
                # print("如果已经翻译过，则直接使用翻译后的文本：\n"+value + "\n" + translatedText)
                logging.info(f"已翻译：{value} -> {translatedText}")
            else:
                try:
                # 如果没有翻译过，则调用翻译函数
                    translatedText = dptrans(text=value, api_key=api_key, base_url=base_url, model=model, hint=hint)
                    logging.info(f"翻译：{value} -> {translatedText}")
                except Exception as e:
                    print("翻译API调用出错")
                    ex = Exception("翻译API调用出错", e)
                    raise ex
                # 将翻译后的文本加入到translatedJson中，由于使用了concurrent.futures并发执行，因此需要加锁
                # translatedJson[value] = translatedText
                # 这里使用了一个简单的锁机制，实际使用中可以使用更复杂的锁机制 
            # 将翻译后的文本加入到translatedJson中，使用锁保护共享字典
                with translation_lock:
                    translatedJson[value] = translatedText
                    # 定期保存翻译结果到文件
                    if len(translatedJson) % 5 == 0:  # 每翻译10个新词条保存一次
                        save_translation_json()
                
            # 原文本下换行然后加入翻译文本
            if onlyChs:
                # 如果只输出中文，则不添加原文本
                jsonData[key] = translatedText
            elif "Radio" in key:
                # 如果是Radio类型的文本，则不添加换行符
                jsonData[key] = value + translatedText
            else:
                jsonData[key] = value + "\n" + translatedText
            #
    ## 将翻译后的json数据写入文件
    # with open(os.path.join("./jsonfiles", os.path.split(jsonPath)[1]), "w", encoding="utf-8") as f:
    #     json.dump(jsonData, f, ensure_ascii=False, indent=4)  # indent=4表示缩进4个空格
    with open(jsonPath, "w", encoding="utf-8") as f:
        json.dump(jsonData, f, ensure_ascii=False, indent=4)  # indent=4表示缩进4个空格
    print("文件翻译完成——" + jsonPath)
    
def transyytg_con(api_key, base_url, model, hint, removeJson, mizPath, onlyChs):

    # mizPath = "E:/miz-translator/back/"  # 任务路径
    targetFileInZip = "l10n/DEFAULT/dictionary"
    fileList = get_files(mizPath)
    print(fileList)  # 打印文件列表
    
    # 遍历文件列表，解压缩文件
    for file in fileList:
        extract_specific_file(file, targetFileInZip, os.path.basename(file) + ".json", output_dir=mizPath)
    
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
        
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(fileList), int(os.cpu_count()//2 + 0.5))) as executor:
        # 创建任务字典，用于跟踪任务
        future_to_file = {}
        
        # 提交所有任务到线程池
        try:
            for file in jsonList:
                future = executor.submit(readAndTranslateJson, file, api_key, base_url, model, hint, onlyChs)
                future_to_file[future] = file
        except Exception as e:
            print("出错")
            ex = Exception("提交任务时出错", e)
            raise ex
        
        # 处理任务结果
        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                future.result()  # 获取结果，如果有异常会抛出
                logging.info(f"成功处理文件: {file}")
            except Exception as e:
                logging.error(f"处理文件 {file} 时出错: {e}")
                raise e
                
    for file in fileList:
        intract.dictionary_intract(file + ".json")
        print("正在合并文件:" + file)
        if removeJson:
            os.remove(file + ".json")
            print("删除文件:" + file + ".json")
        
    print("翻译完成!!!!!")
    
    return True
