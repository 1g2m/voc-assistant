# -*- coding: utf-8 -*-
"""
v1.1 功能增量自动化测试（AppTest）
==================================
a. 导航「📖 自助服务」：expander 存在且含「知识条目」字样。
b. 反馈分析页：筛选负面差评 → 生成回复话术非空且含致歉/抱歉类字样。
c. 工单进度查询：直接落盘 2h 前 / 3 天前的假工单，断言侧栏分别显示
   「已提交」「维修服务进行中」；测后清理假工单文件。

运行方法（在项目根目录）：
    ZHIPU_API_KEY=... .venv/Scripts/python.exe scripts/test_v11.py
"""

import datetime    # 构造假工单的提交时间
import json    # 写假工单文件
import os    # 读写/删除假工单文件
import sys    # 导入路径

from pathlib import Path    # 定位项目根与示例数据

from streamlit.testing.v1 import AppTest    # Streamlit 官方应用测试工具

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from service_core import TICKET_DIR, load_kb    # noqa: E402

SAMPLE = ROOT / "data" / "sample_feedback.xlsx"


# ---------- 直接落盘一个假工单，提交时间改为 hours_ago 小时前 ----------
def make_fake_ticket(ticket_id, hours_ago, problem="测试工单"):
    submitted = (datetime.datetime.now() - datetime.timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
    ticket = {
        "联系人": "测试用户", "手机号": "13800000000", "城市": "测试市",
        "家电类型": "洗衣机", "型号": "未填写", "问题描述": problem,
        "工单编号": ticket_id, "提交时间": submitted,
    }
    os.makedirs(TICKET_DIR, exist_ok=True)
    path = Path(os.path.join(TICKET_DIR, f"{ticket_id}.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ticket, f, ensure_ascii=False, indent=2)
    return path


def test_selfhelp():
    print("===== 自助服务手册页 =====")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception, f"页面运行异常：{at.exception}"
    at.radio[0].set_value("📖 自助服务")
    at.run()
    assert not at.exception, f"自助服务页异常：{at.exception}"

    kb = load_kb()
    # AppTest 只暴露当前选中类型的 expander（默认第一个类型=洗衣机，共 6 条）
    expander_labels = [e.label for e in at.expander]
    print(f"expander 数量：{len(expander_labels)}")
    assert len(at.expander) >= 1, "未渲染任何 expander"
    assert any("知识条目" in str(c.value) for c in at.caption), "expander 内缺「知识条目」小字"
    assert any("WM-01" in lbl for lbl in expander_labels), f"未找到 WM-01 expander：{expander_labels[:5]}"

    # 切到「通用政策」，验证政策条目同版式展示
    type_box = [s for s in at.selectbox if s.label == "选择家电类型"][0]
    type_box.select("通用政策")
    at.run()
    assert not at.exception, f"切换家电类型异常：{at.exception}"
    policy_labels = [e.label for e in at.expander]
    print(f"通用政策 expander：{policy_labels}")
    assert any("PL-01" in lbl for lbl in policy_labels), f"未找到政策条目 expander：{policy_labels}"
    print("自助服务页测试通过 ✅")


def test_negative_reply():
    print("\n===== 反馈分析页差评话术 =====")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.run()
    at.radio[0].set_value("📊 反馈分析")
    at.run()
    at.file_uploader[0].set_value((SAMPLE.name, SAMPLE.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    at.run()
    analyze_buttons = [b for b in at.button if "开始分析" in b.label]
    analyze_buttons[0].click()
    at.run()
    assert not at.exception, f"分析过程异常：{at.exception}"

    # 明细筛选出负面（此时不需要 LLM；生成话术需要 key，运行环境提供）
    senti_box = [s for s in at.selectbox if s.label == "情感"][0]
    senti_box.select("负面")
    at.run()
    assert not at.exception, f"明细筛选异常：{at.exception}"

    pick_box = [s for s in at.selectbox if s.label == "选择要生成回复话术的差评"]
    assert pick_box, "未找到差评选择框（可能没有负面反馈）"
    gen_buttons = [b for b in at.button if "生成客服回复话术" in b.label]
    assert gen_buttons, "未找到生成话术按钮"
    gen_buttons[0].click()
    at.run()
    assert not at.exception, f"生成话术异常：{at.exception}"

    draft = at.session_state.get("差评话术")
    print(f"话术：{(draft or '')[:80]}…")
    assert draft and draft.strip(), "回复话术为空"
    assert any(kw in draft for kw in ["致歉", "歉意", "抱歉", "对不起", "不好意思"]), "话术缺致歉类字样"
    print("差评话术测试通过 ✅")


def test_ticket_query():
    print("\n===== 工单进度查询 =====")
    today = datetime.date.today().strftime("%Y%m%d")
    id_new = f"SI-{today}-9001"
    id_old = f"SI-{today}-9002"
    p1 = make_fake_ticket(id_new, 2)      # 2 小时前 → 已提交 · 待派单
    p2 = make_fake_ticket(id_old, 72)     # 3 天前 → 维修服务进行中
    try:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
        at.run()
        assert not at.exception, f"页面运行异常：{at.exception}"

        # 查询辅助：AppTest 中 form 内 text_input 的 set_value 不跨 run 持久化，
        # 需每次重新获取组件，set_value + click 后一次性 run 提交表单
        def query_ticket(value):
            box = [i for i in at.text_input if "工单进度查询" in i.label][0]
            box.set_value(value)
            btn = [b for b in at.button if "查询进度" in b.label][0]
            btn.click()
            at.run()

        # 查询 2h 前的工单
        query_ticket(id_new)
        assert not at.exception, f"工单查询1异常：{at.exception}"
        success_texts = " ".join(str(s.value) for s in at.success)
        print(f"查询1 success：{success_texts[:120]}")
        assert "已提交" in success_texts, f"2h 工单未显示「已提交」：{success_texts}"

        # 查询 >48h 的工单
        query_ticket(id_old)
        assert not at.exception, f"工单查询2异常：{at.exception}"
        success_texts = " ".join(str(s.value) for s in at.success)
        print(f"查询2 success：{success_texts[:120]}")
        assert "维修服务进行中" in success_texts, f"72h 工单未显示「维修服务进行中」：{success_texts}"

        # 查询不存在的工单号 → 侧栏 warning
        query_ticket(f"SI-{today}-9999")
        warn_texts = " ".join(str(w.value) for w in at.warning)
        print(f"查询3 warning：{warn_texts[:80]}")
        assert "未找到该工单号" in warn_texts, "未显示未找到提示"
        print("工单查询测试通过 ✅")
    finally:
        # 测后清理假工单
        for p in (p1, p2):
            if p.exists():
                p.unlink()
                print(f"已清理假工单：{p.name}")


def main():
    test_selfhelp()
    test_negative_reply()
    test_ticket_query()
    print("\nv1.1 全部测试通过 ✅")


if __name__ == "__main__":
    main()
