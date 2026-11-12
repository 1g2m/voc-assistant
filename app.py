# -*- coding: utf-8 -*-
"""
西门子售后智能客服 v1.0（演示项目，Streamlit 网页版）
====================================================
双模块导航：
  1. 💬 在线客服：故障知识库检索 + LLM 生成回复 + 一键报修工单（scripts/service_core）
  2. 📊 反馈分析：原客户之声分析功能原样迁移（scripts/feedback_core），功能零变化

运行方法（在项目根目录）：
    streamlit run app.py
"""

import datetime    # 周报生成时间、导出文件名
import io     # Excel 导出的内存字节流
import os     # 读环境变量里的 API Key（不使用 check_api_key，它抛 SystemExit 会杀掉网页进程）
import sys    # 把 scripts/ 加入导入路径，便于复用两个 core 模块
from pathlib import Path    # 定位 scripts 目录

import altair as alt    # 声明式统计图表（环形图与分布柱状图）
import pandas as pd    # 读 Excel、筛选明细
import streamlit as st
from zhipuai import ZhipuAI    # 智谱 SDK，网页内自建客户端

# app.py 在项目根，core 在 scripts/ 下，手动补上导入路径
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from feedback_core import analyze_one, build_report    # noqa: E402
from service_core import create_ticket, generate_reply, load_kb, retrieve_kb, route_question    # noqa: E402

st.set_page_config(page_title="西门子家电 · 售后智能客服", page_icon="🔧", layout="wide")

APP_VERSION = "v1.0 · Powered by GLM"

# 快捷问题 chips
QUICK_QUESTIONS = ["洗衣机不脱水", "冰箱不制冷", "预约维修", "保修政策"]

# 判定回复是否需要展示报修表单的关键词
REPAIR_KEYWORDS = ("申请报修", "转人工", "报修流程", "建议报修", "报修")

# =====================================================================
# 品牌样式（西门子风格 · 全深色沉浸版）
# 色板：底 #0A1622 / 次底 #0D1F2C / 亮青 #2CCBDA / hover 青 #1FB3C2 /
#       助手气泡 #12303B / 用户气泡 #00646E / 卡片边 #1E4A55 / 卡片底 #0E2E36 /
#       正文 #D6E4E8 / 次级字 #9FB6BD
# =====================================================================
BRAND_CSS = """
<style>
    /* 隐藏 Streamlit 默认工具栏/页脚/菜单 */
    header[data-testid="stHeader"] {display: none;}
    footer[data-testid="stFooter"] {display: none;}
    #MainMenu {visibility: hidden;}

    /* ---------- 顶部通告条（主区最上，全宽亮青底深字） ---------- */
    .siemens-notice {
        background: #2CCBDA; color: #06222B;
        text-align: center; font-size: 12.5px; font-weight: 600;
        padding: 6px 12px; margin: -1rem -1rem 0.75rem -1rem;
    }

    /* ---------- hero：全深色沉浸背景 + 右上亮青光晕 ---------- */
    .siemens-hero {
        background: radial-gradient(ellipse 620px 420px at 92% 0%, rgba(44,203,218,.22), transparent 60%),
                    linear-gradient(155deg,#050D18 0%,#0B2333 40%,#0E3D4A 72%,#0F5257 100%);
        margin: 0 -1rem; padding: 28px 36px;
    }
    .siemens-hero .hero-brand-row {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 18px;
    }
    .siemens-hero .brand-left {display: flex; align-items: center; gap: 16px;}
    .siemens-hero .siemens-wordmark {
        font-weight: 700; text-transform: uppercase; letter-spacing: 6px;
        color: #2CCBDA; font-size: 26px;
    }
    .siemens-hero .divider {
        width: 1px; height: 24px; background: rgba(214,228,232,.45); display: inline-block;
    }
    .siemens-hero .app-title {color: #FFFFFF; font-weight: 700; font-size: 1.15rem;}
    .siemens-hero .hero-pill {
        color: #2CCBDA; border: 1px solid #2CCBDA; background: transparent;
        border-radius: 999px; padding: 5px 16px; font-size: 0.82rem; white-space: nowrap;
    }
    .siemens-hero .hero-hint {
        display: inline-block; color: #D6E4E8; border: 1px solid rgba(214,228,232,.55);
        background: transparent; border-radius: 999px;
        padding: 6px 18px; font-size: 0.86rem; margin: 4px 0 18px 0;
    }
    .siemens-hero .hero-title {
        color: #FFFFFF; font-weight: 700; font-size: 34px; line-height: 1.25;
    }
    .siemens-hero .hero-sub {
        color: #9FC6CE; font-size: 15px; margin-top: 8px;
    }

    /* ---------- 底部 footer（黑底白字） ---------- */
    .siemens-footer {
        background: #000000; text-align: center;
        color: #FFFFFF; font-size: 0.78rem;
        padding: 12px 0; margin: 16px -1rem 0 -1rem;
    }

    /* ---------- 侧栏（dark 主题自动深色，仅调品牌字与导航选中态） ---------- */
    .siemens-side-brand {padding: 4px 0 2px 0;}
    .siemens-side-brand .siemens-wordmark {
        color: #2CCBDA; font-weight: 700; text-transform: uppercase;
        font-size: 1rem; letter-spacing: 0.24em;
    }
    .siemens-side-brand .side-sub {
        color: #D6E4E8; font-weight: 600; font-size: 0.95rem; margin-top: 2px;
    }
    .siemens-status {font-size: 0.8rem; color: #9FB6BD; padding: 2px 0 6px 0;}
    .siemens-status .dot {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        background: #2CCBDA; margin-right: 6px;
    }

    /* 侧栏 radio 导航：选中项亮青高亮 */
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        border-radius: 4px; padding: 4px 8px; transition: background 0.15s;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"],
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: rgba(44,203,218,.15); border-left: 3px solid #2CCBDA;
    }

    /* ---------- 聊天区：无卡片，消息直接排在深底上 ---------- */
    div[data-testid="stChatMessage"] {
        background: transparent; border: none; padding: 6px 0;
    }
    div[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
        border-radius: 8px; padding: 12px 16px; font-size: 0.95rem; max-width: 78%;
    }
    /* 用户消息（默认头像为 svg）：气泡 #00646E 白字，右对齐 */
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarContainer"] svg) {
        flex-direction: row-reverse;
    }
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarContainer"] svg) [data-testid="stChatMessageContent"] {
        background: #00646E;
    }
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarContainer"] svg) [data-testid="stChatMessageContent"] * {
        color: #FFFFFF;
    }
    /* 助手消息：气泡 #12303B 浅青灰字，无边框 */
    div[data-testid="stChatMessage"]:not(:has([data-testid="stChatMessageAvatarContainer"] svg)) [data-testid="stChatMessageContent"] {
        background: #12303B; border: none;
    }
    div[data-testid="stChatMessage"]:not(:has([data-testid="stChatMessageAvatarContainer"] svg)) [data-testid="stChatMessageContent"] * {
        color: #D6E4E8;
    }
    /* 头像：assistant 亮青圆底深字「S」，user 深灰蓝圆底亮青字「客」 */
    [data-testid="stChatMessageAvatarContainer"] {
        border-radius: 50%;
        min-width: 32px; min-height: 32px;
        display: flex; align-items: center; justify-content: center;
        overflow: hidden; font-weight: 700;
    }
    [data-testid="stChatMessageAvatarContainer"] svg,
    [data-testid="stChatMessageAvatarContainer"] span {display: none;}
    [data-testid="stChatMessageAvatarContainer"]:has(svg) {
        background: #24384A;
    }
    [data-testid="stChatMessageAvatarContainer"]:has(svg)::after {
        content: "客"; color: #2CCBDA; font-size: 0.85rem; font-weight: 700;
    }
    [data-testid="stChatMessageAvatarContainer"]:not(:has(svg)) {
        background: #2CCBDA;
    }
    [data-testid="stChatMessageAvatarContainer"]:not(:has(svg))::after {
        content: "S"; color: #06222B; font-size: 0.9rem; font-weight: 700;
    }
    /* 输入框聚焦态亮青边 */
    div[data-testid="stChatInput"]:focus-within {
        border-color: #2CCBDA !important;
    }

    /* ---------- 按钮 ---------- */
    /* 快捷问题 chips / 主按钮：亮青实心底深字，hover 深化 */
    button[kind="primary"], button[data-testid="stBaseButton-primary"],
    button[kind="primaryForm"], button[data-testid="stBaseButton-primaryForm"] {
        background-color: #2CCBDA; border-color: #2CCBDA; color: #06222B;
        border-radius: 4px; font-weight: 600;
    }
    button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover,
    button[kind="primaryForm"]:hover, button[data-testid="stBaseButton-primaryForm"]:hover {
        background-color: #1FB3C2; border-color: #1FB3C2; color: #06222B;
    }
    /* 次级按钮：透明底描边亮青字 */
    button[kind="secondary"], button[data-testid="stBaseButton-secondary"],
    button[kind="secondaryForm"], button[data-testid="stBaseButton-secondaryForm"] {
        background: transparent; border: 1px solid #2CCBDA; color: #2CCBDA;
        border-radius: 4px;
    }
    button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover,
    button[kind="secondaryForm"]:hover, button[data-testid="stBaseButton-secondaryForm"]:hover {
        border-color: #1FB3C2; background: rgba(44,203,218,.12); color: #2CCBDA;
    }

    /* ---------- 指标卡：深色底 + 左侧亮青竖条 ---------- */
    [data-testid="stMetric"] {
        background: #0E2E36;
        border: 1px solid #1E4A55;
        border-left: 4px solid #2CCBDA;
        border-radius: 4px;
        padding: 14px 18px;
    }
    [data-testid="stMetricLabel"] p {color: #9FB6BD;}
    [data-testid="stMetricValue"] {color: #D6E4E8; font-size: 1.8rem;}

    /* ---------- 页签：选中亮青加粗 + 下划线 ---------- */
    button[data-bas-webui-tab-title], [data-testid="stTab"] button {
        font-size: 1.0rem; font-weight: 600; color: #9FB6BD;
    }
    button[data-bas-webui-tab-title][aria-selected="true"],
    [data-testid="stTab"] button[aria-selected="true"] {
        color: #2CCBDA; font-weight: 700;
        border-bottom: 2px solid #2CCBDA;
    }

    /* ---------- 报修表单卡片：深色边框 + 深底 ---------- */
    [data-testid="stForm"] {
        background: #0E2E36; border: 1px solid #1E4A55;
        border-radius: 8px;
    }

    /* ---------- AI 摘要框：深色底 + 亮青左条 ---------- */
    .siemens-summary {
        background: #0E2E36; border-left: 4px solid #2CCBDA;
        border-radius: 4px; padding: 12px 16px; color: #D6E4E8; font-size: 0.95rem;
    }

    /* ---------- 报修工单号强调 ---------- */
    .siemens-ticket-id {color: #2CCBDA; font-weight: 700; font-size: 1.05rem;}
</style>
"""
st.markdown(BRAND_CSS, unsafe_allow_html=True)


# ---------- 顶部通告条与 footer（主区顶部/底部） ----------
def render_brand_header():
    st.markdown(
        """
        <div class="siemens-notice">
            AI 客服 7×24 在线 · 人工服务 9:00-18:00 · 演示环境非官方
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_brand_footer():
    st.markdown(
        """
        <div class="siemens-footer">
            SIEMENS 家电 · 售后智能客服 ｜ © 2026 AI 演示项目 · 非西门子官方服务 · Powered by GLM-4
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- 分布柱状图辅助函数 ----------
# 统一两个分布图的样式：x 轴标签横排加粗加大（默认竖排难读）、
# 固定像素尺寸（区域不被窗口/双栏布局挤压），数据需含「名称」「数量」两列
def make_distribution_chart(counts_df):
    chart = (
        alt.Chart(counts_df)
        .mark_bar(color="#2CCBDA")
        .encode(
            x=alt.X("名称", sort="-y", axis=alt.Axis(
                labelAngle=0, labelFontWeight="bold", labelFontSize=13, title=None,
                labelColor="#9FB6BD", domainColor="#9FB6BD", tickColor="#9FB6BD")),
            y=alt.Y("数量", axis=alt.Axis(title=None, grid=True, gridColor="#1E4A55",
                                          labelColor="#9FB6BD", domainColor="#9FB6BD",
                                          tickColor="#9FB6BD")),
        )
        .properties(width=420, height=300)
        .configure(background="transparent")
    )
    return chart


# ---------- 明细导出辅助：DataFrame 转 Excel 字节流 ----------
def df_to_excel_bytes(frame):
    buf = io.BytesIO()
    frame.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


# ---------- 情感分布环形图：三色固定，图例放在下方 ----------
def make_sentiment_donut(sentiment_counts):
    source = pd.DataFrame({
        "情感": list(sentiment_counts.keys()),
        "数量": list(sentiment_counts.values()),
    })
    color_scale = alt.Scale(
        domain=["负面", "正面", "中性"],
        range=["#C74634", "#009999", "#9AA5AC"],
    )
    chart = (
        alt.Chart(source)
        .mark_arc(innerRadius=70, outerRadius=120)
        .encode(
            theta=alt.Theta("数量", stack=True),
            color=alt.Color("情感", scale=color_scale, sort=["负面", "正面", "中性"],
                            legend=alt.Legend(labelColor="#9FB6BD")),
            tooltip=["情感", "数量"],
        )
        .properties(width=280, height=280)
        .configure(background="transparent")
    )
    return chart


# ---------- AI 运营摘要：负面 + 未分类条目（截前 15 条）发给 glm-4-flash ----------
def generate_operation_summary(client, results):
    items = [r for r in results if r["情感"] == "负面" or r["类别"] == "未分类"][:15]
    if not items:
        return None
    lines = [f"- [{r['类别']}/{r['情感']}] {r['反馈内容']}" for r in items]
    prompt = f"""以下是本周客户反馈中的负面与未分类条目：
{chr(10).join(lines)}

请输出 80-120 字的中文总结，内容为「本周问题总结与运营建议」，
写成一个自然的段落，不要分点、不要分节、不要打分。"""
    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        # 网络抖动 / 服务异常：优雅降级，摘要不显示
        return None


# =====================================================================
# 模块一：在线客服页
# =====================================================================

# ---------- 渲染报修申请表单（AI 建议转报修时展示） ----------
def render_ticket_form():
    with st.form("报修表单", border=True):
        st.markdown("**📝 报修申请单**")
        st.caption("提交后 24 小时内工程师回电（演示流程）")
        c1, c2 = st.columns(2)
        contact = c1.text_input("联系人 *")
        phone = c2.text_input("手机号 *")
        c3, c4 = st.columns(2)
        city = c3.text_input("城市 *")
        appliance = c4.selectbox("家电类型 *",
                                 ["洗衣机", "冰箱", "洗碗机", "烤箱蒸箱", "灶具", "热水器", "其他"])
        model_no = st.text_input("型号（可不填）")
        description = st.text_area("问题描述 *", placeholder="请补充故障现象、购买时间等")
        submitted = st.form_submit_button("提交报修", type="primary")

    if submitted:
        if not contact.strip() or not phone.strip() or not city.strip() or not description.strip():
            st.warning("请填写带 * 的必填项后再提交。")
            return
        info = {
            "联系人": contact.strip(),
            "手机号": phone.strip(),
            "城市": city.strip(),
            "家电类型": appliance,
            "型号": model_no.strip() or "未填写",
            "问题描述": description.strip(),
        }
        ticket_id, _ = create_ticket(info)
        st.session_state["messages"].append({
            "role": "assistant",
            "content": (
                f"✅ 已收到您的报修申请！工单编号：<span class=\"siemens-ticket-id\">{ticket_id}</span>。\n\n"
                f"我们已登记「{info['家电类型']} · {info['问题描述'][:20]}」问题，"
                "客服专员将在 24 小时内致电您预留的手机号确认上门时间，请保持电话畅通。"
                "（模拟话术，演示项目）"
            ),
        })
        st.session_state["需报修"] = False
        st.rerun()


# ---------- 在线客服主页面 ----------
def render_service_page(client):
    # hero 上半部：品牌字标行（全宽深色渐变 + 右上亮青光晕）
    st.markdown(
        """
        <div class="siemens-hero" style="padding-bottom:6px;">
            <div class="hero-brand-row">
                <div class="brand-left">
                    <span class="siemens-wordmark">SIEMENS</span>
                    <span class="divider"></span>
                    <span class="app-title">家电 · 售后智能客服</span>
                </div>
                <span class="hero-pill">AI 智能诊断 · 知识库可溯源</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 快捷问题 chips（一排按钮，点击即发送）
    chip_cols = st.columns(len(QUICK_QUESTIONS))
    for col, question in zip(chip_cols, QUICK_QUESTIONS):
        if col.button(question, key=f"chip_{question}", type="primary"):
            st.session_state["待发送"] = question
            st.rerun()

    # hero 下半部：指引胶囊 + 大标题块
    st.markdown(
        """
        <div class="siemens-hero" style="padding-top:14px;">
            <div class="hero-hint">! 常见问题智能诊断 · 分步排查 · 一键报修（快捷入口见上，或直接在下方输入）</div>
            <div class="hero-title">西门子家电 · 售后智能客服</div>
            <div class="hero-sub">AI 智能诊断 ｜ 知识库可溯源 ｜ 工单进度可查</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("")

    # 聊天历史（含报修表单触发后的工单确认消息）
    messages = st.session_state.setdefault("messages", [])
    for message in messages:
        avatar = "🔧" if message["role"] == "assistant" else None
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # 底部输入框
    user_input = st.chat_input("请描述您的家电问题，如：洗衣机脱水时异响很大")

    # 快捷按钮与输入框统一走这里处理
    pending = st.session_state.pop("待发送", None) or user_input
    if pending:
        messages.append({"role": "user", "content": pending})
        with st.chat_message("user"):
            st.markdown(pending)

        # 三步过程展示：分类 → 检索 → 生成
        with st.status("正在检索知识库…", expanded=True):
            st.write("① 问题分类（LLM 路由）…")
            route = route_question(client, pending)
            st.write(f"② 知识库检索（{route.get('家电类型')} / {route.get('故障类别')}）…")
            entries = retrieve_kb(load_kb(), route, pending)
            st.write(f"③ 生成回复（命中 {len(entries)} 条知识）…")
            reply = generate_reply(client, pending, messages[:-1], route, entries)
        st.session_state["status_done"] = True

        messages.append({"role": "assistant", "content": reply})
        # 回复含报修引导 → 置位报修表单
        st.session_state["需报修"] = any(kw in reply for kw in REPAIR_KEYWORDS)
        st.rerun()

    # 报修表单：仅在 AI 判断需转报修时展示
    if st.session_state.get("需报修") and messages:
        render_ticket_form()


# =====================================================================
# 模块二：反馈分析页（原 v0.2 逻辑原样迁移，功能零变化）
# =====================================================================
def render_analysis_page(client):
    # ---------- 侧边栏：上传 + 文件信息 + 分析按钮 ----------
    with st.sidebar:
        uploaded = st.file_uploader("上传反馈 Excel（.xlsx，三列：日期/渠道/反馈内容）", type=["xlsx"])

        total_count = valid_count = skipped_count = 0
        valid_rows = []
        df = None

        if uploaded is not None:
            try:
                df = pd.read_excel(uploaded, engine="openpyxl")
            except Exception as e:
                st.error(f"读取 Excel 失败：{e}")
                st.stop()

            if "反馈内容" not in df.columns:
                st.error("缺少「反馈内容」列。表格需包含三列：日期、渠道、反馈内容（列名须完全一致）。")
                st.stop()

            # 空行 / 反馈内容为空的行跳过并计数（逻辑同 scripts/03_analyze_excel.py）
            total_count = len(df)
            for _, row in df.iterrows():
                content = row["反馈内容"]
                if pd.isna(content) or str(content).strip() == "":
                    skipped_count = skipped_count + 1
                    continue
                channel = row["渠道"] if "渠道" in df.columns else ""
                valid_rows.append([channel, str(content).strip()])
            valid_count = len(valid_rows)

            # 文件信息卡
            st.markdown(
                f"""
                <div style="background:#0E2E36;border:1px solid #1E4A55;border-radius:10px;padding:12px 16px;font-size:0.9rem;color:#D6E4E8;">
                    <b>📄 {uploaded.name}</b><br/>
                    总行数：{total_count} ｜ 有效：{valid_count} ｜ 跳过空行：{skipped_count}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.dataframe(df.head(5), width="stretch", height=180)

            if valid_count == 0:
                st.warning("没有可分析的有效反馈（全部为空行）。")

            if st.button("🚀 开始分析", type="primary", width="stretch",
                         disabled=(valid_count == 0)):
                progress = st.progress(0.0, text="准备开始…")
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

                # ---------- 汇总统计 ----------
                negative_count = 0
                uncategorized_count = 0
                for item in results:
                    if item["类别"] == "未分类":
                        uncategorized_count = uncategorized_count + 1
                    elif item["情感"] == "负面":
                        negative_count = negative_count + 1
                analyzed_valid = len(results) - uncategorized_count
                negative_ratio = f"{round(negative_count / analyzed_valid * 100)}%" if analyzed_valid > 0 else "0%"

                # 情感计数（环形图数据）
                sentiment_counts = {"负面": 0, "正面": 0, "中性": 0}
                for item in results:
                    if item["情感"] in sentiment_counts:
                        sentiment_counts[item["情感"]] += 1

                # 分布数据
                results_df = pd.DataFrame(results)
                category_counts = (
                    results_df[results_df["类别"] != "未分类"]["类别"]
                    .value_counts().sort_values(ascending=False)
                )
                channel_counts = results_df["渠道"].value_counts().sort_values(ascending=False)
                category_df = category_counts.rename_axis("名称").reset_index(name="数量")
                channel_df = channel_counts.rename_axis("名称").reset_index(name="数量")

                # 渠道×类别 交叉表（未分类也计入，便于看全貌）
                cross_df = (
                    results_df.groupby(["渠道", "类别"]).size().reset_index(name="数量")
                    if not results_df.empty else pd.DataFrame(columns=["渠道", "类别", "数量"])
                )

                # AI 运营摘要 + 周报（摘要追加到周报末尾）
                summary_text = generate_operation_summary(client, results)
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
                if summary_text:
                    report_content = report_content + "\n\n## AI 运营摘要\n\n" + summary_text + "\n"

                # 结果一次性写入 session_state，切页签不重跑分析；再点按钮即覆盖
                st.session_state["分析结果"] = results
                st.session_state["统计"] = {
                    "success_text": f"{len(results)}/{valid_count}",
                    "negative_ratio": negative_ratio,
                    "uncategorized_count": uncategorized_count,
                    "sentiment_counts": sentiment_counts,
                }
                st.session_state["图表数据"] = {
                    "category_df": category_df,
                    "channel_df": channel_df,
                    "cross_df": cross_df,
                }
                st.session_state["周报内容"] = report_content
                st.session_state["周报文件名"] = f"{datetime.date.today().strftime('%Y-%m-%d')}_周报.md"
                st.session_state["AI摘要"] = summary_text
                st.session_state["源文件名"] = uploaded.name
                st.toast("分析完成 ✅")

    # ---------- 主区：未上传显示欢迎态；已分析则进入四页签 ----------
    results = st.session_state.get("分析结果")

    if results is None:
        if uploaded is not None:
            st.info("文件已上传，点击左侧「🚀 开始分析」开始。")
        st.markdown("### 👋 欢迎使用客户之声分析助手")
        st.markdown(
            "上传客户反馈 Excel，AI 自动分析每条反馈的类别与情感，"
            "生成汇总指标、分布图表、可筛选明细与 Markdown 周报。"
            "\n\n**使用步骤**：在左侧上传文件 → 点击「🚀 开始分析」→ 在页签中查看结果与下载周报。"
        )
        st.markdown("#### 数据格式要求")
        c1, c2, c3 = st.columns(3)
        c1.markdown("**📅 日期**\n\n如 `2026-11-08`")
        c2.markdown("**📍 渠道**\n\n如 `微信` / `电话` / `App`")
        c3.markdown("**💬 反馈内容**\n\n客户原话，不能为空")
        st.markdown("#### 示例数据表格式")
        st.markdown(
            "| 日期 | 渠道 | 反馈内容 |\n"
            "|---|---|---|\n"
            "| 2026-11-08 | 微信 | 维修师傅很专业，很快就修好了 |\n"
            "| 2026-11-09 | 电话 | 下水道堵了两天才有人来处理 |"
        )
        st.caption(f"示例文件：`data/sample_feedback.xlsx` ｜ {APP_VERSION}")
        return

    stats = st.session_state["统计"]
    charts = st.session_state["图表数据"]
    summary_text = st.session_state.get("AI摘要")
    report_content = st.session_state["周报内容"]
    results_df = pd.DataFrame(results)

    tab_overview, tab_detail, tab_chart, tab_report = st.tabs(
        ["📊 总览", "📋 明细", "📈 图表", "📄 周报"])

    # ---------- 页签一：总览 ----------
    with tab_overview:
        m1, m2, m3 = st.columns(3)
        m1.metric("分析成功", stats["success_text"])
        m2.metric("负面占比", stats["negative_ratio"])
        m3.metric("未分类", f"{stats['uncategorized_count']} 条")

        left, right = st.columns([1, 1])
        with left:
            st.altair_chart(make_sentiment_donut(stats["sentiment_counts"]),
                            width="content")
            st.caption("情感分布")

        with right:
            if summary_text:
                st.markdown("#### AI 运营摘要")
                st.markdown(
                    f'<div class="siemens-summary">{summary_text}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("#### AI 运营摘要")
                st.caption("本期没有生成 AI 运营摘要（没有负面/未分类反馈，或模型调用失败）。")

    # ---------- 页签二：明细（筛选 + 搜索 + 导出） ----------
    with tab_detail:
        f1, f2, f3 = st.columns(3)
        cat_choice = f1.selectbox("类别", ["全部"] + sorted(
            [c for c in results_df["类别"].unique() if c != "未分类"]) + ["未分类"])
        senti_choice = f2.selectbox("情感", ["全部", "负面", "正面", "中性"])
        chan_choice = f3.selectbox("渠道", ["全部"] + sorted(results_df["渠道"].astype(str).unique()))
        keyword = st.text_input("🔍 关键词搜索（反馈内容）", placeholder="输入关键词，如：维修")

        filtered = results_df
        if cat_choice != "全部":
            filtered = filtered[filtered["类别"] == cat_choice]
        if senti_choice != "全部":
            filtered = filtered[filtered["情感"] == senti_choice]
        if chan_choice != "全部":
            filtered = filtered[filtered["渠道"].astype(str) == chan_choice]
        if keyword.strip():
            filtered = filtered[filtered["反馈内容"].str.contains(keyword.strip(), na=False)]

        # 负面行整行标红底提示（用 pandas Styler，实现取简）
        def _negative_row_style(row):
            if row["情感"] == "负面":
                return ["background-color: #fdecea; color: #b3261e;"] * len(row)
            return [""] * len(row)

        styler = filtered.style.apply(_negative_row_style, axis=1)
        st.dataframe(styler, width="stretch", height=420)
        st.caption(f"筛选结果：{len(filtered)} / {len(results_df)} 条")

        export_name = f"分析明细_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
        # AppTest 无法读取 download_button 的数据载荷，同步存一份到 session_state 供测试断言
        st.session_state["导出数据"] = df_to_excel_bytes(filtered)
        st.session_state["导出文件名"] = export_name
        st.download_button(
            "⬇️ 导出 Excel 明细",
            data=df_to_excel_bytes(filtered),
            file_name=export_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=len(filtered) == 0,
        )

    # ---------- 页签三：图表 ----------
    with tab_chart:
        g1, g2 = st.columns(2)
        with g1:
            st.altair_chart(make_distribution_chart(charts["category_df"]), width="content")
            st.caption("类别分布")
        with g2:
            st.altair_chart(make_distribution_chart(charts["channel_df"]), width="content")
            st.caption("渠道分布")

        st.markdown("#### 渠道 × 类别 堆叠柱状图")
        if not charts["cross_df"].empty:
            stacked = (
                alt.Chart(charts["cross_df"])
                .mark_bar()
                .encode(
                    x=alt.X("渠道:N", axis=alt.Axis(labelAngle=0, labelFontWeight="bold",
                                                    labelFontSize=13, title=None,
                                                    labelColor="#9FB6BD", domainColor="#9FB6BD",
                                                    tickColor="#9FB6BD")),
                    y=alt.Y("数量:Q", axis=alt.Axis(title=None, grid=True, gridColor="#1E4A55",
                                                    labelColor="#9FB6BD", domainColor="#9FB6BD",
                                                    tickColor="#9FB6BD")),
                    color=alt.Color("类别:N", scale=alt.Scale(
                        range=["#2CCBDA", "#009999", "#00CCCC", "#66CCCC", "#8FBFC7"]),
                        legend=alt.Legend(title=None, labelColor="#9FB6BD")),
                    tooltip=["渠道", "类别", "数量"],
                )
                .properties(width=680, height=320)
                .configure(background="transparent")
            )
            st.altair_chart(stacked, width="content")
        else:
            st.caption("暂无可展示的交叉数据。")

    # ---------- 页签四：周报 ----------
    with tab_report:
        st.markdown(report_content)
        st.download_button(
            "📥 下载周报（Markdown）",
            data=report_content,
            file_name=st.session_state["周报文件名"],
            mime="text/markdown",
        )


# =====================================================================
# 应用入口：API Key 检查 + 侧边栏导航 + 双模块分发
# =====================================================================

# ---------- API Key 检查：必须绕开 core 里基于 SystemExit 的 check_api_key ----------
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

# ---------- 侧边栏：品牌字标 + 在线状态 + 导航 + 版本 ----------
with st.sidebar:
    st.markdown(
        """
        <div class="siemens-side-brand">
            <div class="siemens-wordmark">SIEMENS</div>
            <div class="side-sub">售后智能客服</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="siemens-status">
            <span class="dot"></span>智能客服在线 · 人工服务 9:00-18:00
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "功能导航",
        ["💬 在线客服", "📊 反馈分析"],
        key="nav_page",
    )

    # 新会话按钮：清空客服对话状态
    if st.button("🗑️ 新会话", width="stretch"):
        st.session_state.pop("messages", None)
        st.session_state.pop("需报修", None)
        st.session_state.pop("待发送", None)
        st.rerun()

    st.caption(APP_VERSION)

# ---------- 主区分发：品牌页头 → 页面 → footer ----------
render_brand_header()
if page == "💬 在线客服":
    render_service_page(client)
else:
    render_analysis_page(client)
render_brand_footer()
