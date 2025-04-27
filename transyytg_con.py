## python 创建虚拟环境
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

parser = argparse.ArgumentParser(description="一个命令行参数")

### 模型参数
api_key = None
mizPath = None
removeJson = False 
base_url = "https://api.deepseek.com"
model = "deepseek-chat"
hint = "你是一个翻译，下面是跟战斗机任务（DCS模拟飞行游戏）想关的英语，翻译成简体中文，不要使用markdown输出, 保持原文的换行格式，仅作为翻译不要续写，原文和翻译词数不能相差过大。"
onlyChs = False


def create_introduction():
    """创建介绍文件"""
    introduction = r"""
    这是一个用于翻译DCS任务文件的工具，使用DeepL API进行翻译。
    使用方法：
    1. 同目录config.json为配置文件，初次运行后自动创建
    2. 在配置文件中输入API Key和任务文件夹路径（这是必填项）
        各参数值说明如下：
        api_key: 大模型翻译的key
        base_url: 大模型翻译的地址
        hint: 大模型翻译的提示语
        path: 任务文件夹路径
        remove: 翻译完成后是否删除json文件，默认值为False
        onlyChs: 只输出中文，默认值为False，False表示输出原文和翻译后的文本，True表示只输出翻译后的文本
    3. 运行脚本，翻译完成后会在原文件夹下生成翻译后的json文件
    4. 翻译完成后如果需要删除json文件，请在配置文件中设置remove为True
    
    ## 翻译模型说明，模型调用方法为openAI库，查看使用的api是否支持，本程序调用方法如下：
    ##  client = OpenAI(api_key=api_key, base_url=base_url)
    ##  response = client.chat.completions.create(
    ##      model=model,
    ##      messages=[
    ##          {"role": "user", "content": text},
    ##      ],
    ##      stream=False
    ##  )
    
    同目录中config.json编写参考(多行的话手动在后面加\n换行符，否则会报错，如下面hint中有3行ddd，得这样写)。
    路径得用双斜杠\\，或者直接用/，否则会报错。:
    {
        "api_key": "YOUR_API_KEY",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "hint": "dddddddddd\ndddddddddddddd\nddddddddddddddddddddddd",
        "remove": false,
        "path": "E:/miz-translator\\back/",
        "onlyChs": false
    }
    
    
    同目录下的.cache目录下有翻译记录和日志文件，翻译记录为translated.json，日志文件为log.txt。
    翻译记录为json格式，key为原文本，value为翻译后的文本。日志文件为txt格式，记录了翻译的进度和错误信息。
    如果感觉之前的翻译不准确，可以删除翻译记录文件translated.json，重新运行脚本。
    这样会重新翻译所有的文本。否则会跳过已经翻译过的文本，直接使用translated.json中的翻译结果。
    """
    print(introduction)
    with open("软件使用说明.txt", "w", encoding="utf-8") as f:
        f.write(introduction)

### 创建json配置文件
def load_or_create_config():
    config_path = "./config.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {
            "api_key": "",
            "path": "",
            "remove": False,
            "model": model,
            "base_url": base_url,
            "hint": hint
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        create_introduction()
        print("软件使用说明和配置文件创建成功，请在config.json中输入API Key和任务文件夹路径")
        os.system("pause")  # 只有Windows有效
        sys.exit(1)
        
    return config

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
    

# Create a lock for the shared dictionary
translation_lock = threading.Lock()


def get_jsonList(mizPath):
    # 获取当前路径下的json文件
    jsonList = []
    for root, dirs, files in os.walk(mizPath):
        for file in files:
            if file.endswith(".json"):
                jsonList.append(os.path.join(root, file))
    return jsonList

def readAndTranslateJson(jsonPath):
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
            print(f"翻译进度：{count}/{len(jsonData)} of {jsonPath}")
        if "Name" in key:
            continue  # 跳过Name字段
        if "DictKey" in value:
            continue
        if isMatchLua(value):
            # 如果value是lua函数，则跳过翻译
            print("value是lua函数跳过翻译：\n"+ value)
            translatedJson[value] = ""
            continue
        if len(value) < 2:
            continue
        # 处理文本
        if isinstance(value, str):
            ## 判断是否已经翻译过，translatedJson为字典，key为原文本，value为翻译后的文本
            if check_translation_exists(value):
                # 如果已经翻译过，则直接使用翻译后的文本
                translatedText = translatedJson[value]
                print("如果已经翻译过，则直接使用翻译后的文本：\n"+value + "\n" + translatedText)
            else:
                # 如果没有翻译过，则调用翻译函数
                translatedText = dptrans(text=value, api_key=api_key, base_url=base_url, model=model, hint=hint)
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
    

    ## 命令行输入相关路径，以参数的形式传入
if __name__ == "__main__":
    ## 命令行输入相关路径，以参数的形式传入
    # parser.add_argument("--api_key", type=str, help="DeepL API Key")
    # parser.add_argument("--path", type=str, help="Path to the mission files")
    # ## 帮助
    # # parser.add_argument("--help", action="help", help="input --api_key and --path\nFor example: xxx.exe --api_key YOUR_API_KEY --path E:/miz-translator/back/")
    print("本软件为翻译DCS任务文件的工具，使用大模型 API进行翻译，使用前请阅读软件使用说明.txt")
    print("作者：YATEIFEI（https://github.com/YaTaiphy/）")
    print("联系方式：l476579487@126.com")
    try:
        config = load_or_create_config()
        # 读取配置文件中的参数,其中字符串用引号包裹，去除引号
        api_key = config["api_key"]
        model = config["model"]
        base_url = config["base_url"]
        hint = config["hint"]
        removeJson = config["remove"]
        mizPath = config["path"]
        onlyChs = config["onlyChs"]
        
        
        print(f"API Key: {api_key}")
        print(f"模型: {model}")
        print(f"模型地址: {base_url}")
        print(f"提示语: {hint}")
        print(f"翻译文件夹路径: {mizPath}")
        print(f"翻译完成是否删除原文件: {removeJson}")
        print(f"只输出中文: {onlyChs}")
        
        
        if not api_key or not mizPath:
            print("请在配置文件中输入API Key和任务文件夹路径")
            print("按任意键退出...")
            os.system("pause")  # 只有Windows有效
            sys.exit(1)
        if not isinstance(removeJson, bool):
            print("remove参数值错误，请输入True或False")
            print("按任意键退出...")
            os.system("pause")
            sys.exit(1)
    except Exception as e:
        print("请检查配置文件编写情况，或者重新创建配置文件")
        print("按任意键退出...")
        os.system("pause")  # 只有Windows有效
        sys.exit(1)
    
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
    
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(fileList), os.cpu_count() + 4)) as executor:
        # 创建任务字典，用于跟踪任务
        future_to_file = {}
        
        # 提交所有任务到线程池
        for file in jsonList:
            future = executor.submit(readAndTranslateJson, file)
            future_to_file[future] = file
        
        # 处理任务结果
        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                future.result()  # 获取结果，如果有异常会抛出
                logging.info(f"成功处理文件: {file}")
            except Exception as e:
                logging.error(f"处理文件 {file} 时出错: {e}")
                
    for file in fileList:
        intract.dictionary_intract(file + ".json")
        print("翻译完成，正在合并文件:" + file)
        if removeJson:
            os.remove(file + ".json")
            print("删除文件:" + file + ".json")
        
    print("翻译完成!!!!!")

    print("按任意键退出...")
    os.system("pause")  # 只有Windows有效
    