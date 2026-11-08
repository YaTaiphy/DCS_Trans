# DCS Mission Translator — DCS任务翻译工具

将 DCS World `.miz` 任务文件从英文翻译为简体中文，使用 DeepSeek v4 Pro 大模型 API。

---

## 目录

- [功能特点](#功能特点)
- [处理链路](#处理链路)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [安装](#安装)
- [使用方法](#使用方法)
- [输出格式](#输出格式)
- [缓存系统](#缓存系统)
- [军事术语处理](#军事术语处理)
- [配置持久化](#配置持久化)
- [构建 EXE](#构建-exe)
- [常见问题](#常见问题)

---

## 功能特点

| 功能 | 说明 |
|------|------|
| **提取与翻译** | 解包 `.miz`（ZIP），提取 `l10n/DEFAULT/dictionary`，LLM 翻译后写回 `l10n/CN/dictionary` |
| **多线程并发** | 线程池并发翻译多个 JSON，默认根据 CPU 核心自动调节，可手动指定 |
| **多文件夹** | 支持一次指定多个任务文件夹，跨文件夹并发处理 |
| **进度显示** | 实时进度条，ETA 预估，成功/失败即时反馈 |
| **LLM 超时重试** | 180s 超时 + 3次指数退避重试，单文件失败不影响其余任务 |
| **本地缓存优先** | MD5 内容寻址，命中即返回（毫秒级），无网络依赖 |
| **远程社区缓存** | 可选的社区共享服务器，补充本地未命中条目 |
| **Lua 感知过滤** | 自动跳过 Lua 函数调用、变量声明、表构造器、Do...End 块 |
| **动态术语注入** | 扫描待翻译文本，从 97 条军事术语库中提取相关条目注入提示词 |
| **后处理校正** | 翻译后自动修正：保留术语被误翻译的还原，漏翻的 brevity 补译 |
| **翻译回滚** | 一键移除 `l10n/CN/dictionary`，恢复原始英文任务 |
| **配置持久化** | API Key、路径、偏好选项自动保存，下次交互模式直接回车使用 |
| **缓存自动迁移** | `md5_` 前缀命名，旧格式自动识别重命名，渐进迁移不丢数据 |
| **日志轮转** | 运行日志自动轮转（单文件 1MB，保留 5 个历史） |

---

## 处理链路

```
.miz 文件 (ZIP)
    │
    ▼
┌─────────────────────────────────┐
│ 1. extract_specific_file()      │  extract_miz.py
│    解包 l10n/DEFAULT/dictionary │  Lua 表 → JSON
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ 2. filter_translatable()        │  lua_reg.py
│    跳过: Name字段 / DictKey引用  │
│          Lua代码 / 短于2字符     │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ 3. compute_content_hash()       │  MD5 → "md5_{32位hex}"
└──────────────┬──────────────────┘
               ▼
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐  ┌──────────────┐
│ 本地缓存命中 │  │ 本地缓存未命中 │
│ 即时返回     │  │              │
│ ↓ 后台回填远程│  │ ↓ 查远程缓存  │
└─────────────┘  │ (可选)       │
                 │ ↓ 远程命中   │
                 │ 存入本地     │
                 │ ↓ 远程未命中  │
                 └──────┬───────┘
                        ▼
┌─────────────────────────────────┐
│ 4. build_dynamic_glossary_prompt│  glossary.py
│    扫描原文 → 匹配97条术语库     │
│    → 构建针对性术语附录          │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ 5. LLM_trans_v2()               │  LLM_trans.py
│    静态提示词 + 动态术语段        │  DeepSeek v4 Pro
│    180s 超时 + 3次重试           │  reasoning_effort=high
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ 6. 解析 <input_id> XML 标签     │  regex 提取
│    空结果 → 保存 raw 到 debug   │
│    部分缺失 → warning           │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ 7. correct_translations()       │  glossary.py
│    Pass 1: keep术语还原         │  防空压制→SEAD
│    Pass 2: translate术语补译    │  winchester→弹药耗尽
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ 8. apply_translations()         │  按字段类型混排
│    write_translation_ref()      │  写 _translateRef.json
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ 9. dictionary_intract()         │  intract_miz.py
│    JSON → Lua 表                │  写入 .miz 的 l10n/CN/
└─────────────────────────────────┘
    │
    ▼
.miz 文件 (已翻译)
```

### 缓存查找优先级

```
本地缓存 (瞬时) → 远程缓存 (网络补充) → LLM 翻译 (API)
```

本地优先确保已有翻译零延迟返回；远程作为社区补充仅在本地未命中时查询。

### 多线程处理

多个 JSON 文件通过线程池并发翻译，默认线程数 = `max(1, min(CPU核心数-1, 8))`，可通过 `--threads N` 自定义。

---

## 项目结构

```
DCS_Trans/
├── transyytg_con_cl.py        # 主程序入口 (CLI + 交互模式)
├── fix_translate.py           # 翻译修正合并工具
├── requirements.txt           # Python 依赖
├── readme.md                  # 项目文档 (本文件)
├── util/
│   ├── __init__.py
│   ├── config.py              # 持久化配置 (API key/路径/偏好)
│   ├── extract_miz.py         # .miz 提取 (ZIP → JSON)
│   ├── glossary.py            # 动态术语注入 + 后处理校正
│   ├── intract_miz.py         # .miz 回写 (JSON → Lua → ZIP)
│   ├── LLM_trans.py           # LLM API 客户端 (超时/重试) (DeepSeek v4 Pro)
│   ├── lua_reg.py             # Lua 代码检测 (正则匹配)
│   ├── military_glossary.json # 97条军事术语 (6类别, 结构化)
│   ├── output.py              # 线程安全输出 + 进度条
│   ├── remote_cache.py        # 远程社区缓存客户端 (HTTP)
│   ├── rollback.py            # 翻译回滚 (移除 CN 字典)
│   └── system_prompt.py       # 静态系统提示词
└── cache/                     # 本地缓存 (gitignored)
    ├── config.json            # 持久化配置
    ├── trans.log              # 运行日志 (自动轮转)
    ├── md5_*_translated.json  # 内容寻址翻译缓存
    └── md5_*_raw.txt          # LLM 原始响应 (调试)
```

---

## 环境要求

- Python 3.8+
- [DeepSeek API Key](https://platform.deepseek.com/)
- DCS World `.miz` 任务文件

---

## 安装

```bash
git clone https://github.com/YaTaiphy/DCS_Trans.git
cd DCS_Trans
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1
# 或 Git Bash
source .venv/Scripts/activate

pip install -r requirements.txt
```

---

## 使用方法

### 命令行模式

```bash
# 基本翻译（单文件夹）
python transyytg_con_cl.py --api-key sk-your-key --path "E:/DCS/Missions"

# 多文件夹同时翻译
python transyytg_con_cl.py --api-key sk-your-key --path ./m1 ./m2 "E:/DCS/Missions"

# 指定 4 个线程
python transyytg_con_cl.py --api-key sk-your-key --path ./missions --threads 4

# 仅中文输出
python transyytg_con_cl.py --api-key sk-your-key --path ./missions --only-chs

# 翻译后删除中间 JSON 文件
python transyytg_con_cl.py --api-key sk-your-key --path ./missions --remove-json

# 离线模式（不使用远程缓存）
python transyytg_con_cl.py --api-key sk-your-key --path ./missions --no-remote

# 完整选项
python transyytg_con_cl.py --api-key sk-your-key --path ./m1 ./m2 --threads 8 --only-chs --remove-json
```

| 参数 | 说明 |
|------|------|
| `--api-key` | DeepSeek API Key |
| `--path` | 包含 .miz 的文件夹路径（可多个，空格分隔） |
| `--threads` | 并发线程数（0=自动，范围 1-16） |
| `--only-chs` | 仅输出中文（默认中英混排） |
| `--remove-json` | 翻译后删除中间 JSON 文件 |
| `--no-remote` | 禁用远程缓存 |
| `--rollback` | 回滚翻译，恢复英文 |

### 交互模式

```bash
python transyytg_con_cl.py
```

首次运行时逐项输入，之后每次显示 `[默认: xxx]`，直接回车使用上次保存的值：

```
============================================================
当前模型: deepseek-v4-pro (固定)
远程缓存: 已启用
============================================================
请输入API Key [默认: ********cdef]:           ← 回车使用已保存
默认路径: E:/DCS/Missions
使用默认路径？(回车=是, 输入任意内容=手动输入):   ← 回车使用默认

# 如果选择手动输入：
请输入任务文件夹路径（每行一个，空行结束）:
E:\DCS World\Mods\campaigns
G:\Missions\F-14A
                                             ← 空行结束
找到 5 个.miz文件（2 个文件夹）
是否中英文混排？(y/n, 默认=混排):
是否删除中间JSON文件？(y/n, 默认=否):
是否使用远程缓存服务器？(y/n, 默认=启用):
并发线程数? [回车=自动(7), 范围 1-16]:
```

### 翻译回滚

```bash
# 移除中文翻译，恢复原始英文任务
python transyytg_con_cl.py --rollback --path "E:/DCS/Missions"

# 回滚多个文件夹
python transyytg_con_cl.py --rollback --path ./m1 ./m2
```

### 修正翻译

翻译完成后，手动编辑 `_translateRef.json` 修正错误翻译，然后合并：

```bash
python fix_translate.py /path/to/missions
```

---

## 输出格式

| 字段类型 | 中英混排 (`默认`) | 仅中文 (`--only-chs`) |
|---------|------------------|---------------------|
| 普通文本 | `原文\n译文` | `译文` |
| Radio 字段 | `[原文][译文]` | `译文` |
| Script 字段 | `原文[译文]` | `[Script]译文` |

---

## 缓存系统

### 本地缓存 (`./cache/`)

| 文件 | 说明 |
|------|------|
| `md5_{hash}_translated.json` | 内容寻址翻译结果（解析后的 dict） |
| `md5_{hash}_raw.txt` | LLM 原始响应（调试用） |
| `{hash}_translated.json` | 旧版缓存（首次访问时自动迁移为 `md5_` 前缀） |
| `config.json` | 持久化配置 |
| `trans.log` | 运行日志（自动轮转，1MB×5） |

### 远程社区缓存

- 可通过 `--no-remote` 或在交互模式中选择禁用
- 角色：社区补充，不阻塞本地即时命中
- 翻译结果上传供社区复用，同时受益于他人已翻译内容

### 缓存迁移

```
查找: md5_{hash}_translated.json → {hash}_translated.json → 自动 rename
```

旧格式首次碰到即自动重命名为新格式，渐进迁移无需干预。

---

## 军事术语处理

三层防御保障术语翻译正确：

| 层级 | 时机 | 机制 |
|------|------|------|
| **静态提示词** | 每次 LLM 调用 | 核心规则 + 翻译示例 (~4200 chars) |
| **动态术语注入** | LLM 调用前 | 扫描原文，从 97 条术语中匹配，注入针对性指导 (~100-500 chars) |
| **后处理校正** | LLM 调用后 | 自动修正 keep 术语误翻译 + 补译遗漏的 brevity |

术语库文件：[util/military_glossary.json](util/military_glossary.json) — 6 个类别，97 条结构化术语。

---

## 配置持久化

配置文件 `./cache/config.json`（已 gitignore）：

```json
{
  "api_key": "sk-xxxx",
  "path": "E:/DCS/Missions, G:/Missions/F-14A",
  "only_chs": false,
  "remove_json": false,
  "use_remote_cache": true,
  "threads": 0
}
```

- `threads`: 0 表示自动，根据 CPU 核心数计算（上限 8）
- 命令行模式：选项自动保存
- 交互模式：确认后保存所有选项
- API Key 显示时遮罩：`********cdef`

---

## 构建 EXE

### PyInstaller

```bash
pip install pyinstaller
pyinstaller -F transyytg_con_cl.py -i favicon.ico
```

### Nuitka（推荐，性能更好）

```bash
pip install nuitka

nuitka --standalone --onefile \
  --enable-plugin=upx \
  --upx-binary="F:\AWCSMARK\upx-5.1.1-win64\upx.exe" \
  --windows-icon-from-ico=./favicon.ico \
  --lto=yes \
  --include-data-files=util/military_glossary.json=util/military_glossary.json \
  --output-filename="transyytg_con_cl v2.3.exe" transyytg_con_cl.py
```

> **注意**：`--include-data-files` 必须包含 `military_glossary.json`，否则打包后的 exe 找不到术语库。exe 运行时会在自身所在目录创建 `cache/` 存放配置和缓存，与源代码目录隔离。

---

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| 找不到 .miz 文件 | 确认路径正确，.miz 文件在指定目录中 |
| 翻译过程报错 | 检查 API Key 余额：platform.deepseek.com |
| 远程服务器不可用 | 自动回退本地缓存 + LLM，不影响使用；也可 `--no-remote` 主动禁用 |
| 翻译质量不佳 | 编辑 `_translateRef.json` 手动修正，运行 `fix_translate.py` 合并 |
| 想恢复英文 | `--rollback --path "..."` 一键回滚 |
| LLM 返回无法解析 | 原始输出保存为 `*_parse_error.txt`，可查看调试 |
| 部分条目未翻译 | 查看 warning 数量，通常因为条目被过滤（Lua代码、过短文本） |
| 旧缓存文件未迁移 | 下次运行时自动识别并重命名，不影响翻译结果 |
| LLM 调用超时 | 自动重试最多 3 次（3s/6s/12s 退避），单文件失败不中止整个任务 |
| 打包后运行报错找不到文件 | Nuitka 需加 `--include-data-files` 包含术语库 JSON |
| exe 双击没反应 | 在命令行中运行查看错误输出；确保 exe 所在目录可写（会创建 cache/） |

---

## 版本历史

| 版本 | 说明 |
|------|------|
| v2.3 | 多线程并发翻译、多文件夹支持、LLM 超时重试、进度条、日志轮转、线程安全输出、Nuitka 打包 |
| v2.2 | 回滚功能、配置持久化、远程缓存可选、本地缓存优先、动态术语注入 |
| v2.1 | CLI 重构（移除 GUI）、缓存自动迁移、术语后处理校正 |
| v2.0 | 远程缓存服务器、本地缓存优化 |
| v1.0 | 初始版本 |

## 作者

**YATEIFEI** — [GitHub](https://github.com/YaTaiphy/)

联系：l476579487@126.com | QQ群：1033517336

## 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)
