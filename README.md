# 西门子家电售后智能客服（演示项目）

**🌐 在线演示**：<https://1g2m-voc-assistant-app-jgtv8n.streamlit.app/>

基于 LLM + 本地故障知识库的家电售后客服系统：对话式故障诊断、分点排查指引、报修工单；内置客户反馈批量分析模块。

> ⚠️ AI 演示项目，非西门子官方服务。知识库为模拟资料。

## 功能

### 💬 在线客服（主页）
- **对话诊断**：描述故障（如「冰箱不凉了」）→ AI 自动识别家电类型/故障类别/紧急度
- **知识库驱动**：检索 `knowledge/appliance_kb.json`（25 条：洗衣机/冰箱/洗碗机/烤箱蒸箱/灶具/热水器 + 保修政策），排查步骤来自知识库、不编造
- **安全优先**：燃气类问题前置安全警示（开窗、关阀、勿开关电器）
- **报修工单**：自助排查无效 → 表单收集信息 → 生成工单 `SI-YYYYMMDD-XXXX` 落盘 `data/tickets/`
- **快捷问题**：常见故障一键发送；会话可重置

### 📊 反馈分析（第二模块）
- Excel 批量上传（日期/渠道/反馈内容）→ LLM 分类与情感判断（守门校验/重问/降级）
- 总览指标 + 情感环形图 + AI 运营摘要；明细筛选（类别/情感/渠道/关键词）+ Excel 导出
- 类别/渠道分布图表 + 渠道×类别交叉分析；Markdown 周报生成与下载

## 技术栈

Python 3.12 · Streamlit · zhipuai SDK（glm-4-flash-250414，免费模型）· Altair · pandas · openpyxl

## 快速开始

```bash
.venv\Scripts\python -m pip install -r requirements.txt
set ZHIPU_API_KEY=你的key          # bigmodel.cn 免费申请
.venv\Scripts\streamlit run app.py
```

云端部署：环境变量不可用时自动读取 Streamlit Secrets（`ZHIPU_API_KEY = "..."`）。

## 目录结构

```
app.py                    # 入口：双模块导航（客服/分析）
scripts/service_core.py   # 客服引擎：路由/知识检索/回复生成/工单
scripts/feedback_core.py  # 分析引擎：分类/守门/统计/周报
knowledge/appliance_kb.json  # 故障知识库（演示用）
data/tickets/             # 报修工单存档
data/sample_feedback.xlsx    # 反馈分析示例数据
```

## 设计说明

- **回复可靠性**：系统提示词约束排查步骤只能来自检索到的知识条目，检索为空时引导人工而非编造
- **输出守门**：分类/路由等结构化输出全项校验，异常降级不中断
- **随机性**：LLM 输出存在随机性，周报数字以生成时间快照为准
