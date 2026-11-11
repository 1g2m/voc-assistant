# -*- coding: utf-8 -*-
"""
service_core：西门子家电售后 AI 客服引擎（演示）
================================================
复用 feedback_core 的 zhipuai 调用模式（ask→剥壳→解析 JSON），
但独立实现，不依赖 feedback_core 的分析函数。

  - load_kb()        ：读取 knowledge/appliance_kb.json 知识库
  - route_question() ：LLM 对用户问题分类（家电类型/故障类别/紧急度/在范围内）
  - retrieve_kb()    ：知识检索：家电类型过滤 + 症状关键词命中数排序，取 top2
  - generate_reply() ：生成客服回复（共情→排查步骤→安全提示→必要时转报修）
  - create_ticket()  ：生成工单编号并落盘 data/tickets/编号.json
"""

import datetime    # 工单编号日期部分
import json        # 读知识库、解析 AI 返回
import os          # 工单目录创建与落盘
import random      # 工单编号随机 4 位

from zhipuai import ZhipuAI   # 智谱 SDK

# 项目根目录（本文件在 scripts/ 下，根在上一级）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(ROOT, "knowledge", "appliance_kb.json")
TICKET_DIR = os.path.join(ROOT, "data", "tickets")

VALID_URGENCY = ["高", "中", "低"]


# ---------- 读取知识库 ----------
def load_kb():
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- 调用一次模型并解析 JSON（含剥壳，模式同 feedback_core.ask_once） ----------
def _ask_json(client, prompt):
    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content

        # AI 常用 ```json ... ``` 包裹结果，解析前先剥壳
        clean = answer.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0]
        clean = clean.strip()

        return json.loads(clean)
    except Exception:
        return None


# ---------- 问题分类：LLM 判断家电类型/故障类别/紧急度/是否在服务范围 ----------
def route_question(client, text):
    prompt = f"""你是西门子家电售后的后台分类器（演示）。请对下面的用户问题分类，只输出 JSON，不要输出其他内容。
- 家电类型：从 洗衣机/冰箱/洗碗机/烤箱蒸箱/灶具/热水器/通用/其他 中选一个，无法判断用「其他」
- 故障类别：简短描述问题类别（如「不脱水」「报错」「政策咨询」），若与家电售后无关填「无关」
- 紧急度：高（燃气泄漏/漏水严重/漏电风险等安全隐患）、中（影响正常使用）、低（咨询保养/政策类）
- 在范围内：问题与西门子家电售后相关为 true；问手机、天气、闲聊等无关问题为 false

用户问题：{text}

输出格式：
{{"家电类型": "...", "故障类别": "...", "紧急度": "高/中/低", "在范围内": true}}"""
    result = _ask_json(client, prompt)
    # 兜底：分类失败时保守放行到知识检索，回复层再收敛
    if not isinstance(result, dict):
        return {"家电类型": "其他", "故障类别": "未分类", "紧急度": "低", "在范围内": True}
    if result.get("紧急度") not in VALID_URGENCY:
        result["紧急度"] = "中"
    result["在范围内"] = bool(result.get("在范围内"))
    return result


# ---------- 知识检索：家电类型过滤 → 症状关键词命中数排序 → top2 ----------
def retrieve_kb(kb, route, text):
    text = text.strip().lower()
    kb_type = route.get("家电类型", "其他")

    scored = []
    for entry in kb.get("条目", []):
        # 政策类条目（家电类型=通用）始终可命中参与排序
        if entry["家电类型"] != "通用" and entry["家电类型"] != kb_type:
            continue
        hits = 0
        for kw in entry["症状关键词"]:
            # 双向子串匹配：口语「脱不干」也能命中关键词「不脱水」所属类目
            if kw.lower() in text or text in kw.lower():
                hits += 1
        if hits > 0:
            scored.append((hits, entry))

    # 命中数从多到少排序，取前 2 条
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:2]]


# ---------- 生成客服回复 ----------
# 角色要求：共情一句→分点排查步骤（只来自检索条目）→安全提示→紧急/未命中时引导报修；
# 范围外问题礼貌说明只服务家电售后。语气专业简洁，200 字内。
def generate_reply(client, text, history, route, entries):
    # 检索条目摘要拼进 prompt，明确禁止编造步骤
    if entries:
        kb_lines = []
        for entry in entries:
            kb_lines.append(
                f"【{entry['症状']}】可能原因：{'、'.join(entry['可能原因'])}；"
                f"排查步骤：{'；'.join(entry['排查步骤'])}；"
                f"安全提示：{entry['安全提示']}"
            )
        kb_text = "\n".join(kb_lines)
    else:
        kb_text = "（未检索到匹配条目）"

    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '客服'}：{m['content']}"
        for m in history[-6:]    # 只带最近 3 轮，控制 token
    )

    system_prompt = """你是「西门子家电售后智能客服（演示）」，服务范围仅限西门子家电售后。
回复结构要求：
1. 先共情一句；
2. 分点给出排查步骤，步骤只能来自提供的知识库内容，不得编造步骤；
3. 如有安全提示，必须原样给出；
4. 若紧急度为高或知识库未检索到条目，明确建议转人工报修，并引导用户申请报修（提及「申请报修」表单）；
5. 若问题与家电售后无关，礼貌说明你只服务西门子家电售后；
6. 语气专业简洁，每次回复 200 字以内。"""

    user_prompt = f"""历史对话：
{history_text if history_text else "（无）"}

知识库检索结果：
{kb_text}

分类结果：家电类型={route.get('家电类型')}，故障类别={route.get('故障类别')}，紧急度={route.get('紧急度')}，在范围内={route.get('在范围内')}

用户新问题：{text}

请按角色要求输出回复。"""
    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reply = (response.choices[0].message.content or "").strip()
        return reply or "抱歉，当前客服系统繁忙，请稍后重试或申请报修。"
    except Exception:
        return "抱歉，客服系统暂时无法响应，建议您直接申请报修，我们会在24小时内回电。"


# ---------- 报修工单：编号 SI-YYYYMMDD-XXXX，落盘 data/tickets/ ----------
def create_ticket(info):
    date_str = datetime.date.today().strftime("%Y%m%d")
    serial = f"{random.randint(0, 9999):04d}"
    ticket_id = f"SI-{date_str}-{serial}"

    ticket = dict(info)
    ticket["工单编号"] = ticket_id
    ticket["提交时间"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs(TICKET_DIR, exist_ok=True)
    path = os.path.join(TICKET_DIR, f"{ticket_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ticket, f, ensure_ascii=False, indent=2)

    return ticket_id, ticket
