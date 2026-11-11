# -*- coding: utf-8 -*-
"""
app.py (v0.2) 的自动化冒烟测试
==============================
用 streamlit.testing.v1.AppTest 模拟上传 data/sample_feedback.xlsx，
触发「🚀 开始分析」，断言四个页签、指标卡、AI 摘要、明细筛选与下载按钮。

运行方法（在项目根目录）：
    .venv/Scripts/python.exe scripts/test_app.py
"""

import re    # 从文案里提取有效条数
import sys    # 确保能导入根目录的 app.py

from pathlib import Path    # 定位项目根与示例数据

from streamlit.testing.v1 import AppTest    # Streamlit 官方应用测试工具

# 让测试脚本能 import 根目录的 app 模块（scripts/ 的子目录视角下根在上一级）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMPLE = ROOT / "data" / "sample_feedback.xlsx"


def main():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    # ZHIPU_API_KEY 由运行环境变量提供；模拟文件上传：file_uploader 直接接受本地文件路径
    at.run()    # 先跑一次让导航元素挂载
    assert not at.exception, f"页面运行异常：{at.exception}"
    # v1.0 双模块导航：切到「📊 反馈分析」页
    at.radio[0].set_value("📊 反馈分析")
    at.run()
    assert len(at.file_uploader) == 1, "未找到 file_uploader 组件"
    # set_value 接受 (文件名, 字节内容, MIME 类型) 三元组，模拟真实上传
    at.file_uploader[0].set_value((SAMPLE.name, SAMPLE.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    at.run()

    assert not at.exception, f"页面运行异常：{at.exception}"

    # 点击侧边栏主按钮「🚀 开始分析」
    analyze_buttons = [b for b in at.button if "开始分析" in b.label]
    assert analyze_buttons, "未找到「开始分析」按钮"
    analyze_buttons[0].click()
    at.run()

    assert not at.exception, f"分析过程异常：{at.exception}"

    # 断言四个页签存在
    tab_labels = [t.label for t in at.tabs]
    print("tabs:", tab_labels)
    for expected in ["📊 总览", "📋 明细", "📈 图表", "📄 周报"]:
        assert expected in tab_labels, f"缺页签：{expected}"

    # 断言三枚 metric 出现
    metric_values = [m.value for m in at.metric]
    print("metrics:", metric_values)
    assert len(at.metric) >= 3 and any(metric_values), "未找到 metric 组件"
    success_text = metric_values[0]    # 形如 "20/20"

    # AI 摘要非空，或存在优雅降级提示（「没有生成 AI 运营摘要」）
    caption_texts = " ".join(str(c.value) for c in at.caption)
    success_blocks = " ".join(str(s.value) for s in at.success)
    summary = at.session_state.get("AI摘要")
    print("AI摘要：", (summary or "")[:60], "…")
    assert (summary and summary.strip()) or "没有生成 AI 运营摘要" in caption_texts, \
        "AI 摘要既非空也缺降级提示"

    # 有效行数从 metric 的 "成功/有效" 文案解析（形如 "20/20"）
    m = re.match(r"(\d+)/(\d+)$", success_text)
    assert m, "未找到有效行数文案"
    valid_count = int(m.group(2))

    # 明细页筛选：AppTest 不支持真正切页签，但各页签元素均已挂载，直接操作筛选控件
    report = at.session_state["周报内容"]
    neg_m = re.search(r"负面反馈：(\d+) 条", report)
    assert neg_m, "周报缺负面条数"
    negative_count = int(neg_m.group(1))

    selectboxes = at.selectbox
    senti_box = [s for s in selectboxes if s.label == "情感"][0]
    senti_box.select("负面")
    at.run()
    assert not at.exception, f"明细筛选异常：{at.exception}"
    df_values = [d.value for d in at.dataframe]
    detail_df = [d for d in df_values if "情感" in getattr(d, "columns", [])][-1]
    assert len(detail_df) == negative_count, \
        f"筛选后行数 {len(detail_df)} != 负面数 {negative_count}"
    print(f"明细筛选：情感=负面 → {len(detail_df)} 行（与周报负面数一致）")

    # Excel 下载按钮存在且数据非空（载荷从 session_state 同步读取）
    excel_buttons = [d for d in at.download_button if "Excel" in d.label]
    assert excel_buttons, "未找到 Excel 下载按钮"
    assert excel_buttons[0].label == "⬇️ 导出 Excel 明细", "Excel 按钮文案不符"
    excel_data = at.session_state["导出数据"]
    assert excel_data, "Excel 下载数据为空"
    assert excel_data[:2] == b"PK", "Excel 下载内容不是合法 xlsx（缺 PK 头）"
    print("Excel 下载字节数：", len(excel_data))

    # 周报内容与下载按钮（摘要应已追加在末尾）
    report_buttons = [d for d in at.download_button if "周报" in d.label]
    assert report_buttons, "未找到周报下载按钮"
    assert "客户之声周报" in report and "生成时间" in report, "周报缺标题或生成时间"
    assert f"分析成功：{success_text}" in report, f"周报缺「分析成功：{success_text}」"
    if summary:
        assert "AI 运营摘要" in report, "周报缺 AI 运营摘要段落"
    print("周报文件名：", at.session_state["周报文件名"])

    print(f"✅ 测试通过：有效 {valid_count} 条，负面 {negative_count} 条，无异常")


if __name__ == "__main__":
    main()
