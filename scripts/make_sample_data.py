# -*- coding: utf-8 -*-
"""
生成模拟数据：data/sample_feedback.xlsx
=======================================
作用：造一份 20 行的「客户反馈表」，供 03_analyze_excel.py 使用。
真实项目里这张表是从客服系统导出的，这里先用模拟数据代替。

可以重复运行——每次都会重新随机生成并覆盖旧文件。

运行方法（在项目根目录打开终端）：
    python scripts/make_sample_data.py
"""

import datetime   # 生成「近 7 天」的随机日期
import os         # 创建 data 目录
import random     # 随机挑日期、挑渠道、挑反馈内容
import sys        # 用来把标准输出切到 UTF-8

import pandas as pd   # 表格处理库（pip install pandas openpyxl）

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 兼容 GBK 控制台的 emoji/中文输出

# ---------- 1. 准备三列的候选数据 ----------
# 反馈池：家政公司场景，类别（服务/产品/价格/售后/物流）和情感（正/负/中）都要覆盖到
feedback_pool = [
    "空调加氟之后制冷效果明显好了很多",
    "厨房下水道堵了两天，师傅来了才通开",
    "预约周五上门，结果师傅周六才到",
    "清洗抽油烟机非常仔细，连滤网都拆下来洗了",
    "报价比页面显示贵了两百多，感觉被坑了",
    "维修完一周又漏水，第二次上门还不收钱，态度不错",
    "换的零件是旧的不是全新的，很不满",
    "师傅提前打电话确认时间，服务很专业",
    "卫生间防水重做后还是渗水，要求退款",
    "客服半夜也能接单，第二天就安排了师傅",
    "地漏安装得很整齐，师傅还教了保养方法",
    "保洁阿姨打碎了花瓶，赔偿谈了很久",
    "维修师傅迟到四十分钟也没有道歉",
    "冰箱修好了，收费和报价单完全一致，很放心",
    "预约系统显示有号，实际约不上，体验很差",
    "油烟机清洗后噪音变小了，挺满意",
    "师傅上门穿了鞋套，服务细节到位",
    "同样的故障修了三次还没修好",
    "发票开错了抬头，联系客服三天没人理",
    "安装热水器很快，师傅还主动做了安全检查",
]
# 渠道分布大致 8/6/6：先造一个按比例排好的列表，再打乱
channels = ["微信", "微信", "微信", "微信", "微信", "微信", "微信", "微信",
            "电话", "电话", "电话", "电话", "电话", "电话",
            "APP", "APP", "APP", "APP", "APP", "APP"]

# ---------- 2. 生成 20 行数据 ----------
today = datetime.date.today()
rows = []
for i in range(20):
    # 日期：近 7 天内随机一天
    day = today - datetime.timedelta(days=random.randint(0, 6))
    rows.append({
        "日期": day.strftime("%Y-%m-%d"),
        "渠道": channels[i],
        "反馈内容": feedback_pool[i],
    })
# 渠道跟着行走，但反馈顺序打乱一下，避免每次生成的表完全一样
random.shuffle(rows)

# ---------- 3. 写入 Excel ----------
# engine="openpyxl" 是写 .xlsx 用的引擎，显式写出来更稳
df = pd.DataFrame(rows, columns=["日期", "渠道", "反馈内容"])
os.makedirs("data", exist_ok=True)
df.to_excel("data/sample_feedback.xlsx", index=False, engine="openpyxl")
print(f"✅ 已生成 data/sample_feedback.xlsx（{len(df)} 行）")
