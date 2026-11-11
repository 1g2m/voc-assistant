# -*- coding: utf-8 -*-
"""
单条客户反馈分析
================
调用 glm-4-flash 对一条反馈完成类别归类、情感判断与关键词提取。

用法：
    python scripts/01_first_ai_call.py
"""

import json   # Python 自带的 JSON 处理工具
import os     # 用来读取环境变量（API Key 存在这里，不能写死在代码里）
import sys    # 用来把标准输出切到 UTF-8

from zhipuai import ZhipuAI   # 智谱官方 SDK（pip install zhipuai）

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 兼容 GBK 控制台的 emoji/中文输出

# ---------- 1. 读取 API Key ----------
# Key 放在环境变量里，而不是写在代码里 —— 这是行业规范，防止泄露
api_key = os.environ.get("ZHIPU_API_KEY")
if not api_key:
    print("❌ 没找到 API Key！")
    print("   解决方法（Git Bash）：export ZHIPU_API_KEY=你的key")
    print("   解决方法（CMD）   ：set ZHIPU_API_KEY=你的key")
    raise SystemExit(1)

# ---------- 2. 创建客户端 ----------
client = ZhipuAI(api_key=api_key)

# ---------- 3. 待分析的客户反馈 ----------
# 单条分析入口；批量与文件输入见 02_batch_analyze.py / 03_analyze_excel.py
feedback = "师傅上门倒是挺快的，但是装完第二天就又开始漏水了，打电话报修没人接，太失望了。"

# ---------- 4. 构造提示词（Prompt）----------
# Prompt 三要素：角色（你是谁）+ 任务（做什么）+ 输出格式（怎么给）
prompt = f"""你是一家家政服务公司的客户反馈分析助手。
请分析下面这条客户反馈，只输出 JSON，不要输出任何其他内容。

反馈内容：{feedback}

输出格式：
{{"类别": "服务/产品/价格/售后 中的一个", "情感": "正面/负面/中性", "关键词": ["2-4个关键词"]}}"""

# ---------- 5. 调用模型 ----------
# glm-4-flash：免费模型，适合批量文本分类场景
response = client.chat.completions.create(
    model="glm-4-flash",
    messages=[
        {"role": "user", "content": prompt},
    ],
)

# ---------- 6. 拿到模型的回答 ----------
answer = response.choices[0].message.content
print("AI 原始回答：", answer)

# ---------- 7. 尝试把回答解析成 JSON ----------
# AI 有时候不完全听话：它喜欢用 ```json ... ``` 代码块包裹结果
# 所以解析前先「剥壳」——去掉首尾的 ``` 标记行
clean = answer.strip()
if clean.startswith("```"):            # 第一行是 ```json 就删掉它
    clean = clean.split("\n", 1)[1]
    clean = clean.rsplit("```", 1)[0]  # 结尾的 ``` 也删掉
clean = clean.strip()

try:
    result = json.loads(clean)
    print("\n✅ 解析成功！")
    print(f"   类别  ：{result['类别']}")
    print(f"   情感  ：{result['情感']}")
    print(f"   关键词：{'、'.join(result['关键词'])}")
except json.JSONDecodeError:
    print("\n⚠️ AI 未返回标准 JSON，剥壳后仍解析失败")
