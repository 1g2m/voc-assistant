# -*- coding: utf-8 -*-
"""
feedback_core：客户反馈分析的可复用后端
=======================================
供 Streamlit 前端（app.py 反馈分析模块）复用的分析引擎：
  - ask_once()           ：调用一次 glm-4-flash 并解析 JSON（含「剥壳」）
  - is_valid()           ：类别/情感全项校验
  - analyze_one()        ：分析单条反馈（不合法最多重问 2 次，仍不行降级未分类）
  - build_report()       ：拼接 Markdown 周报内容

注意：不直接运行本文件；API Key 检查与客户端构建由 app.py 负责
（命令行场景的 SystemExit 检查会杀掉网页进程，故不在本模块做）。
"""

import json   # 解析 AI 返回的 JSON 结果

from zhipuai import ZhipuAI   # 智谱官方 SDK（pip install zhipuai）

# 类别和情感都必须是合法词——AI 偶尔会不守规矩（比如答成「售后/物流」）
VALID_CATEGORIES = ["服务", "产品", "价格", "售后", "物流"]
VALID_SENTIMENTS = ["正面", "负面", "中性"]

# ---------- 调用一次模型并解析 ----------
# 网络抖动、AI 输出不规范都会在这里被兜住，返回 None 交给上层决定怎么处理
def ask_once(client, prompt):
    try:
        # glm-4-flash 是智谱的免费模型，批量调用不产生费用
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content

        # AI 喜欢用 ```json ... ``` 包裹结果，解析前先「剥壳」
        clean = answer.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0]
        clean = clean.strip()

        return json.loads(clean)
    except Exception as e:
        # 单条失败很正常，不能让整批中断
        print(f"⚠️ 这条分析失败，跳过：{e}")
        return None

# 检查 AI 的答案两个字段是否都合法（缺字段或值不在候选里都算不合法）
def is_valid(result):
    if result is None:
        return False
    return (result.get("类别") in VALID_CATEGORIES
            and result.get("情感") in VALID_SENTIMENTS)

# 输入反馈原文，输出 {"类别": ..., "情感": ...}
# 最多问 3 次（首次 + 重问 2 次）；全部不合法则降级，保证整批继续跑
def analyze_one(client, feedback):
    # Prompt 三要素：角色 + 任务 + 输出格式；类别五选一（多了「物流」）
    prompt = f"""你是一家家政服务公司的客户反馈分析助手。
请分析下面这条客户反馈，只输出 JSON，不要输出任何其他内容。

反馈内容：{feedback}

输出格式：
{{"类别": "服务/产品/价格/售后/物流 中的一个", "情感": "正面/负面/中性"}}"""

    # 先问第一次，之后不合法就重问，最多 2 次重问
    result = ask_once(client, prompt)
    retries = 0
    while not is_valid(result) and retries < 2:
        retries = retries + 1
        bad = result if result else {}
        # 把模型的错误答案贴回去，让它重新在五个词里选一个
        retry_prompt = f"""你上一次的回答（{json.dumps(bad, ensure_ascii=False)}）不合法。
「类别」只能是 服务/产品/价格/售后/物流 五个词之一；
「情感」只能是 正面/负面/中性 三个词之一。只输出 JSON。

反馈内容：{feedback}

输出格式：
{{"类别": "服务/产品/价格/售后/物流 中的一个", "情感": "正面/负面/中性"}}"""
        result = ask_once(client, retry_prompt)

    if is_valid(result):
        return {"类别": result["类别"], "情感": result["情感"]}
    # 重问 2 次仍然不合法：降级处理，不让这条卡住整个批次
    print(f"⚠️ 这条多次回答都不合法，标记为未分类")
    return {"类别": "未分类", "情感": "未知"}

# ---------- Markdown 周报 ----------
# 把汇总数字拼成 Markdown 报告内容（纯函数：只负责拼字符串，不负责写文件）
# 报告字段用参数区分：source_line / skipped_text / channel 部分可省略
def build_report(now, source_line, success_count, total_count, skipped_text,
                 negative_count, valid_count, uncategorized_count,
                 sorted_categories, footer,
                 sorted_channels=None):
    # 负面占比的分母是有效条数（未分类的没有情感结论，不算进去）
    if valid_count > 0:
        percent = round(negative_count / valid_count * 100)
    else:
        percent = 0

    lines = []
    lines.append("# 客户之声周报")
    lines.append("")
    lines.append(f"生成时间：{now}")
    if source_line:
        lines.append(source_line)
    lines.append("")
    lines.append(f"- 分析成功：{success_count}/{total_count}{skipped_text}")
    lines.append(f"- 负面反馈：{negative_count} 条（占比 {percent}%）")
    # 未分类即使为 0 也写上，看报告的人不用猜「是不是漏统计了」
    lines.append(f"- 未分类：{uncategorized_count} 条")
    lines.append("- 类别分布（从多到少）：")
    for category, count in sorted_categories:
        lines.append(f"  - {category}：{count} 条")
    if sorted_channels:
        lines.append("- 渠道分布（从多到少）：")
        for channel, count in sorted_channels:
            lines.append(f"  - {channel}：{count} 条")
    lines.append("")
    lines.append(footer)
    return "\n".join(lines)
