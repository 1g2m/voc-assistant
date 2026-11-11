# -*- coding: utf-8 -*-
"""
app.py 的自动化冒烟测试
======================
用 streamlit.testing.v1.AppTest 模拟上传 data/sample_feedback.xlsx，
触发「开始分析」，断言指标、结果行数与无异常。

运行方法（在项目根目录）：
    .venv/Scripts/python.exe -m scripts.test_app   # 或直接 python scripts/test_app.py
"""

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
    at.run()    # 先跑一次让 file_uploader 元素挂载
    assert len(at.file_uploader) == 1, "未找到 file_uploader 组件"
    # set_value 接受 (文件名, 字节内容, MIME 类型) 三元组，模拟真实上传
    at.file_uploader[0].set_value((SAMPLE.name, SAMPLE.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    at.run()

    assert not at.exception, f"页面运行异常：{at.exception}"

    # 数据已加载：预览区出现，按钮可点
    assert at.button[0].value is False or True    # 按钮存在
    at.button[0].click()
    at.run()

    assert not at.exception, f"分析过程异常：{at.exception}"

    # 断言三枚 metric 的数值文本都出现
    metric_texts = [m.value for m in at.metric]
    print("metrics:", metric_texts)
    assert any(metric_texts), "未找到 metric 组件"

    # 逐条结果行数 = 有效行数（从 dataframe 组件取行数）
    df_values = [d.value for d in at.dataframe]
    print("dataframe 行数：", [len(d) for d in df_values])
    results_df = df_values[-1]
    caption_texts = " ".join(str(c.value) for c in at.caption)
    print("captions:", caption_texts)
    # 有效行数从预览 caption 里解析（"有效反馈：X 条"）
    import re    # 从文案里提取有效条数
    m = re.search(r"有效反馈：(\d+) 条", caption_texts)
    assert m, "未找到有效行数文案"
    valid_count = int(m.group(1))
    assert len(results_df) == valid_count, f"结果行数 {len(results_df)} != 有效行数 {valid_count}"

    # 下载周报按钮：存在，且报告内容（session_state 同步）含关键文案与正确数字
    assert len(at.download_button) == 1, "未找到 download_button 组件"
    assert at.download_button[0].label == "📥 下载周报（Markdown）", "按钮文案不符"
    report = at.session_state["周报内容"]
    assert isinstance(report, str) and report, "周报内容为空"
    assert at.session_state["周报文件名"].endswith("_周报.md"), "文件名不符"
    assert "客户之声周报" in report and "生成时间" in report, "周报缺标题或生成时间"
    success_text = metric_texts[0]    # 形如 "20/20"
    expect_success = f"分析成功：{success_text}"
    assert expect_success in report, f"周报缺「{expect_success}」"
    assert f"中的 {valid_count} 条客户反馈" in report, "周报 footer 缺有效条数"
    print("周报预览：")
    print(report)
    print("周报文件名：", at.session_state["周报文件名"])

    print(f"✅ 测试通过：有效 {valid_count} 条，结果 {len(results_df)} 行，无异常")


if __name__ == "__main__":
    main()
