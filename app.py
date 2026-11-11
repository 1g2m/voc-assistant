# -*- coding: utf-8 -*-
"""
客户之声分析助手（Streamlit 网页版）
==================================
上传 xlsx（日期/渠道/反馈内容三列），逐条调用 glm-4-flash 分析类别与情感，
网页内展示指标卡、逐条结果与分布图表。分析逻辑复用 scripts/feedback_core。

运行方法（在项目根目录）：
    streamlit run app.py
"""

import datetime    # 周报生成时间与文件名
import os     # 读环境变量里的 API Key（不使用 check_api_key，它抛 SystemExit 会杀掉网页进程）
import sys    # 把 scripts/ 加入导入路径，便于复用 feedback_core
from pathlib import Path    # 定位 scripts 目录

import altair as alt    # 声明式统计图表（streamlit 自带依赖，绘制分布柱状图）
import pandas as pd    # 读 Excel 表格
import streamlit as st
from zhipuai import ZhipuAI    # 智谱 SDK，网页内自建客户端

# app.py 在项目根，core 在 scripts/ 下，手动补上导入路径
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from feedback_core import analyze_one, build_report    # noqa: E402

st.set_page_config(page_title="客户之声分析助手", page_icon="📊", layout="wide")


# ---------- 分布柱状图辅助函数 ----------
# 统一两个分布图的样式：x 轴标签横排加粗加大（默认竖排难读）、
# 固定像素尺寸（区域不被窗口/双栏布局挤压），数据需含「名称」「数量」两列
def make_distribution_chart(counts_df):
    chart = (
        alt.Chart(counts_df)
        .mark_bar(color="#4f8bf9")
        .encode(
            x=alt.X("名称", sort="-y", axis=alt.Axis(
                labelAngle=0, labelFontWeight="bold", labelFontSize=13, title=None)),
            y=alt.Y("数量", axis=alt.Axis(title=None, grid=True, gridColor="#e6e6e6")),
        )
        .properties(width=420, height=300)
    )
    return chart

st.title("📊 客户之声分析助手")
st.caption("上传客户反馈 Excel，AI 自动分析每条反馈的类别与情感，并生成汇总指标与分布图表。")

# ---------- 1. API Key 检查：必须绕开 core 里基于 SystemExit 的 check_api_key ----------
# 双通道读取：本地优先环境变量 ZHIPU_API_KEY；云端（Streamlit Cloud）则从 secrets 读取。
# 本地无 .streamlit/secrets.toml 时访问 st.secrets 会抛异常，故用 try/except 包住，异常视为无 Key。
api_key = os.environ.get("ZHIPU_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["ZHIPU_API_KEY"]
    except Exception:
        api_key = None
if not api_key:
    st.error(
        "未检测到 ZHIPU_API_KEY，请先设置后刷新页面。\n\n"
        "- 本地：Git Bash `export ZHIPU_API_KEY=你的key`；CMD `set ZHIPU_API_KEY=你的key`\n"
        "- 云端部署：在 Streamlit Cloud 的 Secrets 中配置 ZHIPU_API_KEY"
    )
    st.stop()

client = ZhipuAI(api_key=api_key)

# ---------- 2. 上传并读取 Excel ----------
uploaded = st.file_uploader("上传反馈 Excel（.xlsx，三列：日期/渠道/反馈内容）", type=["xlsx"])
if uploaded is None:
    st.info("请先上传 xlsx 文件。")
    st.stop()

try:
    df = pd.read_excel(uploaded, engine="openpyxl")
except Exception as e:
    st.error(f"读取 Excel 失败：{e}")
    st.stop()

# ---------- 3. 列校验：缺「反馈内容」列直接说明格式要求并停止 ----------
if "反馈内容" not in df.columns:
    st.error("缺少「反馈内容」列。表格需包含三列：日期、渠道、反馈内容（列名须完全一致）。")
    st.stop()

# 空行 / 反馈内容为空的行跳过并计数（逻辑同 scripts/03_analyze_excel.py）
total_count = len(df)
skipped_count = 0
valid_rows = []
for _, row in df.iterrows():
    content = row["反馈内容"]
    if pd.isna(content) or str(content).strip() == "":
        skipped_count = skipped_count + 1
        continue
    channel = row["渠道"] if "渠道" in df.columns else ""
    valid_rows.append([channel, str(content).strip()])
valid_count = len(valid_rows)

st.subheader("数据预览")
st.dataframe(df.head(10), width="stretch")
st.caption(f"总行数：{total_count}，有效反馈：{valid_count} 条（跳过空行 {skipped_count} 行）")

if valid_count == 0:
    st.warning("没有可分析的有效反馈（全部为空行）。")
    st.stop()

# ---------- 4. 开始分析：逐条调用 analyze_one，进度条实时更新 ----------
if st.button("开始分析"):
    progress = st.progress(0.0, text="准备开始…")
    status = st.empty()
    results = []
    for i, (channel, feedback) in enumerate(valid_rows):
        result = analyze_one(client, feedback)
        results.append({
            "序号": i + 1,
            "渠道": channel,
            "类别": result["类别"],
            "情感": result["情感"],
            "反馈内容": feedback,
        })
        progress.progress((i + 1) / valid_count, text=f"分析中 {i + 1}/{valid_count}：{feedback[:20]}")

    status.success(f"分析完成：成功 {len(results)}/{valid_count} 条")

    # ---------- 5. 汇总指标 ----------
    negative_count = 0
    uncategorized_count = 0
    for item in results:
        if item["类别"] == "未分类":
            uncategorized_count = uncategorized_count + 1
        elif item["情感"] == "负面":
            negative_count = negative_count + 1
    analyzed_valid = len(results) - uncategorized_count
    negative_ratio = f"{round(negative_count / analyzed_valid * 100)}%" if analyzed_valid > 0 else "0%"

    col1, col2, col3 = st.columns(3)
    col1.metric("分析成功", f"{len(results)}/{valid_count}")
    col2.metric("负面占比", negative_ratio)
    col3.metric("未分类", f"{uncategorized_count} 条")

    # ---------- 6. 逐条结果与分布图表 ----------
    st.subheader("逐条分析结果")
    st.dataframe(pd.DataFrame(results), width="stretch")

    # 图表区与上方表格拉开距离（Streamlit 无原生 margin，用空白占位 div）
    st.markdown('<div style="height: 48px;"></div>', unsafe_allow_html=True)

    left, right = st.columns(2)
    category_counts = (
        pd.DataFrame(results)[pd.DataFrame(results)["类别"] != "未分类"]["类别"]
        .value_counts()
        .sort_values(ascending=False)
    )
    channel_counts = pd.DataFrame(results)["渠道"].value_counts().sort_values(ascending=False)
    # value_counts 的 Series 转成「名称/数量」两列 DataFrame，交给统一的柱状图函数
    category_df = category_counts.rename_axis("名称").reset_index(name="数量")
    channel_df = channel_counts.rename_axis("名称").reset_index(name="数量")
    left.altair_chart(make_distribution_chart(category_df), use_container_width=False)
    left.caption("类别分布")
    right.altair_chart(make_distribution_chart(channel_df), use_container_width=False)
    right.caption("渠道分布")

    # ---------- 7. 下载周报：复用 feedback_core.build_report，格式与命令行版一致 ----------
    # 网页版不写 reports/ 目录（浏览器下载即得，避免服务器侧副作用），故不用 write_report
    sorted_categories = list(zip(category_df["名称"], category_df["数量"]))
    sorted_channels = [(name, int(cnt)) for name, cnt in channel_counts.items()]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_content = build_report(
        now=now,
        source_line=f"数据来源：{uploaded.name}（读入 {total_count} 行）",
        success_count=len(results),
        total_count=valid_count,
        skipped_text=f"（跳过空行 {skipped_count} 行）",
        negative_count=negative_count,
        valid_count=analyzed_valid,
        uncategorized_count=uncategorized_count,
        sorted_categories=sorted_categories,
        footer=f"数据来源：{uploaded.name} 中的 {valid_count} 条客户反馈（voc-assistant 网页版）",
        sorted_channels=sorted_channels,
    )
    # AppTest 无法读取 download_button 的数据载荷，同步存一份到 session_state 供测试断言
    st.session_state["周报内容"] = report_content
    st.session_state["周报文件名"] = f"{datetime.date.today().strftime('%Y-%m-%d')}_周报.md"
    st.download_button(
        "📥 下载周报（Markdown）",
        data=report_content,
        file_name=f"{datetime.date.today().strftime('%Y-%m-%d')}_周报.md",
        mime="text/markdown",
    )
