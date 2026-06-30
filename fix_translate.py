import os
import json

### 读取文件夹下所有以_translateRef.json结尾的文件
def get_translateRef_jsonList(folderPath):
    # 获取当前路径下的json文件
    jsonList = []
    for root, dirs, files in os.walk(folderPath):
        for file in files:
            if file.endswith("_translateRef.json"):
                jsonList.append(os.path.join(root, file))
    return jsonList

### 寻找.cache/translated.json文件，如果没有则创建一个空的，如果有则读取，将translated.json中同key的value替换为_translateRef.json中的value
def merge_translations(jsonList):
    # 读取或创建translated.json
    translated_path = "./cache/translated.json"
    if os.path.exists(translated_path):
        with open(translated_path, "r", encoding="utf-8") as f:
            translatedJson = json.load(f)
    else:
        translatedJson = {}
        with open(translated_path, "w", encoding="utf-8") as f:
            json.dump(translatedJson, f, ensure_ascii=False, indent=4)
        with open(translated_path, "r", encoding="utf-8") as f:
            translatedJson = json.load(f)

    ## 创建key改编状态
    key_status = []
    # 遍历所有_translateRef.json文件，合并翻译
    for jsonFile in jsonList:
        with open(jsonFile, "r", encoding="utf-8") as f:
            currentJson = json.load(f)
            for key, value in currentJson.items():
                if key in translatedJson and value != translatedJson[key] and key not in key_status:
                    translatedJson[key] = value  # 替换为_translateRef.json中的value
                    key_status.append(key)  # 记录已改编的key，避免重复替换
                elif key not in translatedJson:
                    translatedJson[key] = value  # 新增未存在的key

    # 保存合并后的结果
    with open(translated_path, "w", encoding="utf-8") as f:
        json.dump(translatedJson, f, ensure_ascii=False, indent=4)
    print(f"合并完成，已保存到 {translated_path}")

def fix_translate(folderPath):
    jsonList = get_translateRef_jsonList(folderPath)
    print("找到以下_translateRef.json文件：")
    for jsonFile in jsonList:
        print(jsonFile)
    merge_translations(jsonList)
    print("翻译修复完成！")

if __name__ == "__main__":
    folderPath = "G:\\E\\FROG-7"  # 任务路径
    jsonList = get_translateRef_jsonList(folderPath)
    print("找到以下_translateRef.json文件：")
    for jsonFile in jsonList:
        print(jsonFile)
    merge_translations(jsonList)

