# Please install OpenAI SDK first: `pip3 install openai`

from openai import OpenAI

def dptrans(text, api_key, base_url="https://api.deepseek.com", model = "deepseek-chat",hint = "你是一个翻译，下面是跟战斗机任务（DCS模拟飞行游戏）想关的英语，翻译成简体中文，不要使用markdown输出, 保持原文的换行格式，仅作为翻译不要续写，原文和翻译词数不能相差过大。"):
    # hint="你是一个翻译，下面是跟战斗机任务（DCS模拟飞行游戏）想关的英语，翻译成简体中文，不要使用markdown输出, 保持原文的换行格式，仅作为翻译不要续写，原文和翻译词数不能相差过大。"
    # hint = '''"
    #         你是一个翻译，下面是跟战斗机任务（DCS模拟飞行游戏）想关的英语，翻译成简体中文，不要使用markdown输出, 保持原文的换行格式，仅作为翻译不要续写，不要有注释，原文和翻译词数不能相差过大。
    #         【战术翻译核心规则】
    #         ◆锁定原文：
    #         - 武器码：Fox-[1-3]/Maverick/Magnum
    #         - 呼号：/[A-Z]{2,}\s\d+/
    #         - 坐标数字：全保留
    #         ◆强制转换：
    #         SAM→地空导弹 | splash→命中 | hot→敌对
    #         ◆格式规范：
    #         1. 全角标点（!→！） 
    #         2. 术语间隔符统一（- → -）
    #         ◆处理优先级：
    #         1. 武器/呼号锁定 → 2. 高危词替换 → 3. 格式清理
    #         [正则触发]
    #         武器发射：/\bFox\s[1-3]!?/i
    #         呼号匹配：/[A-Z]{4}\s\d{3}/"'''

    client = OpenAI(api_key=api_key, base_url=base_url)
    # client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions")

    response = client.chat.completions.create(
        model=model,
        # model = "glm-4-plus",
        messages=[
            {"role": "system", "content": hint},
            {"role": "user", "content": "翻译：\n" + text},
        ],
        stream=False
    )

    return response.choices[0].message.content
    
if __name__ == "__main__":
    dptrans("PLAYER: Ravens, comin' right, roll out 120.")