import json
import re


def isMatchLua(text):
    """
    检查输入字符串是否符合特定格式：
    - B部分：不能以数字开头，且不能包含空格
    - A部分：首字符不能是数字或空格，后面可以有任意非空格字符
    - C部分：首字符不能是空格，后面可以有任意非空格字符
    """
    # 正则表达式模式
    # (?!) 负向先行断言，确保B部分不以数字开头
    # [^\s]+? 非贪婪匹配，确保B部分至少有一个非空格字符
    # \. 第一个点
    # [^\s\d][^\s]* A部分：首字符非数字且非空格，后面≥0个非空格字符
    # \. 第二个点
    # [^\s][^\s]* C部分：首字符非空格，后面≥0个非空格字符

    pattern1 = r"""
        (?!\d)       # B不能以数字开头（负向先行断言）
        ([^\s]+?)    # B部分：≥1个非空格字符（非贪婪匹配）
        \.           # 第一个点
        ([^\s\d][^\s]*)  # A部分：首字符非数字且非空格，后面≥0个非空格字符
        \.           # 第二个点
        ([^\s][^\s]*)    # C部分：首字符非空格，后面≥0个非空格字符
    """

    pattern2 = r'[a-zA-Z_][a-zA-Z0-9_]*[.:][a-zA-Z0-9_]{2,}\([^)]*\)'

    # 匹配 Lua 变量声明 + 表构造（如 `local x = {...}`）
    pattern_lua_var = r'(?:^|;|\n)\s*local\s+[a-zA-Z_][a-zA-Z0-9_]*\s*(?:=\s*(?:[^,\s;]+|\{[^\}]*\}|\"[^\"]*\"|\'[^\']*\'|function\s*\([^\)]*\)))?\s*(?=[;\n]|$)'

    # 匹配 Lua 表构造（如 `{ ["key"] = value }`）
    pattern_lua_table = r'\{\s*\[[\'"][^\]]+[\'"]\]\s*=\s*[^\}]+?\}'

    pattern_DOEND = r"\bDo\b(.+?)\bEnd\b"

    if re.search(pattern1, text) or re.search(pattern2, text) or re.search(pattern_lua_var, text) or re.search(
            pattern_lua_table, text) or re.search(pattern_DOEND, text):
        return True
    else:
        return False


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "sss a.aa:des() sss",  # 有效
        "a.b.c",  # 有效
        "测试.部分.匹配",  # 有效（中文）
        "1ab.cd.ef",  # 无效（B以数字开头）
        "ab .cd.ef",  # 无效（B末尾有空格）
        "ab.c d.ef",  # 无效（A包含空格）
        "ab.cd. ef",  # 无效（C以空格开头）
        "ab.1cd.ef",  # 无效（A以数字开头）
        ".X.",  # 无效（各部分长度不足）
        "() .(1) .(2)",  # 有效（特殊字符）
        "N38.23.22",
        "if (Unit.getByName(\"Steep\") and Unit.getByName(\"Steep\"):getFuel() < 0.05)",
        "-- Creats a UH-60 on the helipad of a Hazard perry.\n\nlocal staticObj = {\n    [\"name\"] = \"SEDLO BOW STATICS 2\", -- unit name (Name this something identifiable if you wish to remove it later)\n\n\n-- Copy and paste over this with the units information\n   ",
        "local people going to do",
        "locals",
        "local a = 1",
        "local a = 1, b = 2",
        "local a",
    ]

    for text in test_cases:
        print(f"'{text}': {'匹配' if isMatchLua(text) else '不匹配'}")

    # 读取json文件
    with open("./cache/translated.json", "r", encoding="utf-8") as f:
        translatedJson = json.load(f)
    keys = []
    count = 0
    for key, value in translatedJson.items():
        if isMatchLua(key):
            print(key)
            translatedJson[key] = ""
            keys.append(key)
        # if "getByName" in key or "return true" in key or "destroy()" in key or "trigger.action" in key:
        #     count += 1
        #     print(key)
    # with open("./cache/translated.json", "w", encoding="utf-8") as f:
    #     json.dump(translatedJson, f, ensure_ascii=False, indent=4)
    print(len(keys))
    print(count)
    print("end")