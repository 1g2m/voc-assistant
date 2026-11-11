# -*- coding: utf-8 -*-
"""
读 Excel 批量分析并生成周报
===========================
作用：从 Excel 表里读客户反馈（日期/渠道/反馈内容三列），
逐条交给 AI 分析（类别 + 情感），汇总后自动生成 Markdown 周报。

运行方法（在项目根目录打开终端）：
    python scripts/03_analyze_excel.py               # 默认读 data/sample_feedback.xlsx
    python scripts/03_analyze_excel.py 路径.xlsx     # 也可以指定自己的表
"""

import datetime   # 周报文件名和生成时间用
import os     # 用来把周报写进 reports 目录前确认脚本运行位置
import sys    # 读命令行参数（用户可以指定 Excel 路径）、切换标准输出编码

import pandas as pd    # 读 Excel 表格（pip install pandas openpyxl）

from feedback_core import analyze_one, build_report, check_api_key, print_summary, write_report

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 兼容 GBK 控制台的 emoji/中文输出

# ---------- 1. 检查 API Key 并构建客户端（公共逻辑在 feedback_core 里） ----------
client = check_api_key()

# ---------- 2. 确定要分析的 Excel 文件 ----------
# 命令行第一个参数是文件路径；不传就用默认的示例数据
# len(sys.argv) 是参数个数：只有 1 个说明用户没传路径
if len(sys.argv) > 1:
    xlsx_path = sys.argv[1]
else:
    xlsx_path = "data/sample_feedback.xlsx"

# ---------- 3. 读表 ----------
# engine="openpyxl" 是读 .xlsx 的引擎，显式写出来避免环境差异报错
df = pd.read_excel(xlsx_path, engine="openpyxl")

# 空行 / 反馈内容为空的行没有分析价值，跳过并计数（真实导出的表常有这种脏数据）
# pd.isna 用来判断单元格是不是空的（Excel 里的空格子读进来是 NaN）
skipped_count = 0
valid_rows = []
for index, row in df.iterrows():
    content = row["反馈内容"]
    if pd.isna(content) or str(content).strip() == "":
        skipped_count = skipped_count + 1
        continue
    valid_rows.append([row["渠道"], str(content).strip()])

total_count = len(valid_rows)

# ---------- 4. 主流程：逐条分析（分析逻辑在 feedback_core 里） ----------
# results 只装分析的条目，格式 [渠道, 反馈文本, 类别, 情感]
results = []
for i, (channel, feedback) in enumerate(valid_rows):
    result = analyze_one(client, feedback)
    results.append([channel, feedback, result["类别"], result["情感"]])
    # 输出格式：第N条 [渠道] [类别|情感] 文本前25字（长反馈截断，报告更整齐）
    short_text = feedback[:25]
    print(f"第{i + 1}条 [{channel}] [{result['类别']}|{result['情感']}] {short_text}")

# ---------- 5. 汇总报告（带跳过数与渠道维度，公共逻辑在 feedback_core 里） ----------
stats = print_summary(results, total_count, skipped_count=skipped_count, show_channel=True)

# ---------- 6. 导出 Markdown 周报 ----------
# 汇总数字不能只留在终端里——存成文件才能发群、归档、留档对比
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
today = datetime.date.today()
report_content = build_report(
    now=now,
    source_line=f"数据文件：{xlsx_path}（读入 {len(df)} 行）",
    success_count=stats["success_count"],
    total_count=total_count,
    skipped_text=f"（跳过空行 {skipped_count} 行）",
    negative_count=stats["negative_count"],
    valid_count=stats["valid_count"],
    uncategorized_count=stats["uncategorized_count"],
    sorted_categories=stats["sorted_categories"],
    footer=f"数据来源：{xlsx_path} 中的 {total_count} 条客户反馈（voc-assistant 批量分析）",
    sorted_channels=stats["sorted_channels"],
)
filepath = write_report(report_content, today)

print(f"\n✅ 周报已生成：{filepath}")
