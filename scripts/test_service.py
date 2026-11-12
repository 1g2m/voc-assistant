# -*- coding: utf-8 -*-
"""
service_core 单元自测 + 在线客服页 AppTest 冒烟测试
==================================================
a. AppTest：默认导航为在线客服页，模拟发送「洗衣机不脱水怎么办」断言回复非空且含
   「排查/步骤」类字样；发送「今天天气怎么样」断言含范围外引导（「售后」）；
   快捷按钮与 chat_input 存在；无 exception。
b. 单元：route_question「冰箱不凉了」→ 家电类型=冰箱；retrieve_kb「甩不干」命中
   洗衣机脱水条目；create_ticket 生成文件且编号格式正确（测试后删除）。

运行方法（在项目根目录）：
    ZHIPU_API_KEY=... .venv/Scripts/python.exe scripts/test_service.py
"""

import os    # 校验与删除测试工单文件
import re    # 校验工单编号格式
import sys    # 导入路径

from pathlib import Path    # 定位项目根

from streamlit.testing.v1 import AppTest    # Streamlit 官方应用测试工具

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from service_core import create_ticket, load_kb, retrieve_kb, route_question    # noqa: E402


# ---------- b. 单元自测 ----------
def test_unit():
    print("===== 单元自测 service_core =====")

    kb = load_kb()
    print(f"知识库条目数：{len(kb['条目'])}")
    assert 22 <= len(kb["条目"]) <= 28, "知识库条目数不在 22-28 区间"

    client_ok = os.environ.get("ZHIPU_API_KEY")
    if client_ok:
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=client_ok)
        route = route_question(client, "冰箱不凉了")
        print(f"route_question(冰箱不凉了) → {route}")
        assert route.get("家电类型") == "冰箱", f"路由家电类型错误：{route.get('家电类型')}"
    else:
        print("⚠️ 未设置 ZHIPU_API_KEY，跳过 route_question 联网测试")

    entries = retrieve_kb(kb, {"家电类型": "洗衣机"}, "衣服甩不干")
    print(f"retrieve_kb(甩不干) → {[e['id'] for e in entries]}")
    assert entries, "「甩不干」未命中任何条目"
    assert entries[0]["id"] == "WM-01", f"命中条目不对：{entries[0]['id']}"

    ticket_id, ticket = create_ticket({
        "联系人": "测试用户", "手机号": "13800000000", "城市": "测试市",
        "家电类型": "洗衣机", "型号": "未填写", "问题描述": "单元测试",
    })
    print(f"create_ticket → {ticket_id}")
    assert re.fullmatch(r"SI-\d{8}-\d{4}", ticket_id), f"工单编号格式错误：{ticket_id}"
    path = ROOT / "data" / "tickets" / f"{ticket_id}.json"
    assert path.exists(), "工单文件未落盘"
    path.unlink()
    print(f"测试工单已删除：{path.name}")
    print("单元自测通过 ✅")


# ---------- a. AppTest 冒烟测试（在线客服页） ----------
def test_apptest():
    print("\n===== AppTest 在线客服页 =====")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.run()

    assert not at.exception, f"页面运行异常：{at.exception}"

    # 默认导航为在线客服
    radio = at.radio[0]
    print(f"导航默认值：{radio.value}")
    assert radio.value == "💬 在线客服", f"默认导航不是在线客服：{radio.value}"

    # 快捷按钮与 chat_input 存在
    chips = [b.label for b in at.button if b.label in
             ["洗衣机不脱水", "冰箱不制冷", "预约维修", "保修政策"]]
    print(f"快捷按钮：{chips}")
    assert len(chips) == 4, f"快捷按钮缺失：{chips}"
    assert len(at.chat_input) == 1, "未找到 chat_input"

    # 模拟发送：洗衣机不脱水
    at.chat_input[0].set_value("洗衣机不脱水怎么办").run()
    assert not at.exception, f"发送问题1异常：{at.exception}"

    # 快捷按钮点击冒烟（预约维修 → 政策类）
    chip_btn = [b for b in at.button if b.label == "保修政策"][0]
    chip_btn.click()
    at.run()
    assert not at.exception, f"快捷按钮点击异常：{at.exception}"

    # 模拟发送：范围外问题
    at.chat_input[0].set_value("今天天气怎么样").run()
    assert not at.exception, f"发送问题2异常：{at.exception}"

    # 取 assistant 消息断言：AppTest 不直接暴露 chat 内容，从 session_state 取
    messages = at.session_state["messages"]
    assistant_msgs = [m["content"] for m in messages if m["role"] == "assistant"]
    print(f"assistant 消息数：{len(assistant_msgs)}")
    print(f"回复1（洗衣机不脱水）：{assistant_msgs[0][:120]}...")
    assert assistant_msgs[0], "assistant 回复为空"
    assert any(kw in assistant_msgs[0] for kw in ["排查", "步骤", "检查"]), \
        "回复1缺少排查/步骤类字样"
    assert "依据：知识条目" in assistant_msgs[0], \
        f"回复1缺少可溯源依据行：{assistant_msgs[0][-80:]}"
    print(f"回复（天气）：{assistant_msgs[-1][:120]}...")
    assert "售后" in assistant_msgs[-1], "范围外回复缺少售后引导字样"

    print("AppTest 冒烟测试通过 ✅")


def main():
    test_unit()
    test_apptest()
    print("\n全部测试通过 ✅")


if __name__ == "__main__":
    main()
