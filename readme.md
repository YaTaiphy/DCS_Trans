# 程序说明
用于解包、大模型翻译、打包DCS（数字战斗模拟）的miz文件。

# 程序需求
1、有模型的调用api。

2、使用的模型支持openai库框架下api调用。

# 生成命令行EXE说明
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pyinstaller -F transyytg_con_cl.py -i OIP-C.jpg

# 生成图形
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pyinstaller -F  --windowed transyytg_con_window.py -i OIP-C.jpg
