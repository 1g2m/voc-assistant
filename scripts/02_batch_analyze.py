# -*- coding: utf-8 -*-
"""
批量分析客户反馈
================
作用：把内置示例数据（10 条客户反馈）逐条交给 AI 分析（类别 + 情感），
最后自动汇总——成功多少条、负面占比多少、问题集中在哪类，
作为运营复盘的「反馈体检报告」。

运行方法（在项目根目录打开终端）：
    python scripts/02_batch_analyze.py
"""

import datetime   # Python 自带的日期时间工具，周报文件名和生成时间用
import sys    # 用来把标准输出切到 UTF-8

from feedback_core import analyze_one, build_report, check_api_key, print_summary, write_report

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 兼容 GBK 控制台的 emoji/中文输出

# ---------- 1. 检查 API Key 并构建客户端（公共逻辑在 feedback_core 里） ----------
client = check_api_key()

# ---------- 2. 内置示例数据 ----------
# 一批客户反馈示例；接入真实数据后可换成从 Excel 批量读取
feedbacks = [
    "师傅上门很及时，修得很仔细",
    "厨房水管漏水，地板全泡了",
    "预约两次都改时间，很不方便",
    "空调修好了，师傅态度很好",
    "报价高于市场价",
    "油烟机清洗很干净，满意",
    "师傅约好没来，也没提前打电话",
    "维修还算及时，就是有点贵",
    "卫生间漏水复修了一次才修好",
    "客服很耐心，问题解决了",
]

# ---------- 3. 主流程：逐条分析 ----------
# results 只装分析成功的条目，格式 [反馈文本, 类别, 情感]
results = []
for i, feedback in enumerate(feedbacks):
    result = analyze_one(client, feedback)
    if result is None:
        continue
    results.append([feedback, result["类别"], result["情感"]])
    # 输出格式：第N条 [类别|情感] 反馈文本（编号从 1 开始，运营看报告更直观）
    print(f"第{i + 1}条 [{result['类别']}|{result['情感']}] {feedback}")

# ---------- 4. 汇总报告（公共逻辑在 feedback_core 里，02 无渠道维度） ----------
total_count = len(feedbacks)
stats = print_summary(results, total_count)

# ---------- 5. 导出 Markdown 周报 ----------
# 汇总数字不能只留在终端里——存成文件才能发群、归档、留档对比
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
today = datetime.date.today()
report_content = build_report(
    now=now,
    source_line=None,
    success_count=stats["success_count"],
    total_count=total_count,
    skipped_text="",
    negative_count=stats["negative_count"],
    valid_count=stats["valid_count"],
    uncategorized_count=stats["uncategorized_count"],
    sorted_categories=stats["sorted_categories"],
    footer="数据来源：本周 10 条客户反馈（voc-assistant 批量分析）",
)
filepath = write_report(report_content, today)

print(f"\n✅ 周报已生成：{filepath}")
