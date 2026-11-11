# 客户之声分析助手（VoC Assistant）

基于 LLM 的客户反馈批量分析工具：读取反馈数据，自动完成类别归类与情感判断，输出结构化周报。

## 功能

- **单条分析**（`scripts/01_first_ai_call.py`）：一条反馈 → 类别 / 情感 / 关键词
- **批量分析**（`scripts/02_batch_analyze.py`）：内置数据集批量分析，含输出质量守门
- **Excel 批量分析**（`scripts/03_analyze_excel.py`）：读取 xlsx 数据源，支持渠道维度汇总，自动生成 Markdown 周报
- **网页版**（`app.py`）：Streamlit 在线分析——上传 xlsx、实时进度、指标卡、类别/渠道分布图表、一键下载周报
- **报告输出**：`reports/YYYY-MM-DD_周报.md`（按日命名，含汇总与渠道分布）

## 技术栈

Python 3.12 · zhipuai SDK（glm-4-flash）· pandas · openpyxl

## 快速开始

```bash
# 1. 安装依赖
.venv\Scripts\python -m pip install -r requirements.txt

# 2. 配置 API Key（bigmodel.cn 免费申请，建议 setx 持久化）
set ZHIPU_API_KEY=你的key

# 3. 运行（缺省读取 data/sample_feedback.xlsx）
.venv\Scripts\python scripts/03_analyze_excel.py [数据文件.xlsx]
```

## 目录结构

```
scripts/   分析脚本
data/      反馈数据（xlsx）
reports/   生成的周报
```

## 设计说明

- **输出守门**：模型结果须通过校验（类别五选一、情感三选一），不合法则重问（至多 2 次），仍不合法降级为「未分类」，单列统计、不计入占比分母
- **稳定性**：单条分析异常不中断整批；写文件统一 UTF-8
- **随机性**：LLM 输出存在随机性，报告数字以文件内「生成时间」快照为准
