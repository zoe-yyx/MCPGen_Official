# AI-Powered Recruitment Pipeline: CV Screening to Interview Scheduler

MCP项目，将n8n工作流转换为基于FastMCP的Python项目。自动化候选人评估全流程：从CV提交到面试安排。

## 工作流程

1. **Webhook - Receive CV** - 接收候选人简历提交（模拟）
2. **Airtable - Store Candidate** - 存储候选人记录（模拟）
3. **Airtable - Get Job Requirements** - 获取职位要求（模拟）
4. **HTTP Request - Download CV** - 下载简历内容（模拟）
5. **AI - Extract CV Data** - GPT提取简历结构化数据（技能、学历、经验）
6. **AI Agent - Qualification Assessment** - GPT评估候选人资质（评分、推荐）
7. **Airtable - Update Assessment** - 更新评估结果到数据库（模拟）
8. **Filter - Qualified Candidates** - 筛选合格候选人（非Reject）
9. **AI Agent - Generate Email** - GPT生成个性化招聘邮件
10. **Send Email - Candidate Outreach** - 发送邮件（模拟）
11. **Filter - Interview Candidates** - 筛选面试候选人
12. **Google Calendar - Schedule Interview** - 安排面试日历（模拟）
13. **Slack - Send Notification** - Slack通知招聘团队（模拟）
14. **Airtable - Update Interview Details** - 更新面试信息（模拟）
15. **Respond to Webhook** - 返回处理结果

## 注意事项

- Airtable、Google Calendar、Gmail、Slack均为**Mock模式**
- OpenAI API为**真实调用**，使用gpt-5.1模型（3次AI调用：提取CV、评估资质、生成邮件）
- 简历内容为预设的模拟数据
- 筛选不通过时自动跳过后续邮件/面试步骤

## 环境配置

```bash
cp .env.template .env
# 编辑 .env 填入 API 密钥
```

## 安装依赖

```bash
uv sync
```

## 运行Server

```bash
uv run python mcp_server/server.py
```

## 执行Workflow

```bash
uv run python run_workflow.py
```

## 运行测试

```bash
uv run python -m pytest tests/test_tools.py -v
```

## 项目结构

```
mcp_project67/
├── README.md
├── .env / .env.template
├── pyproject.toml
├── run_workflow.py              # 主工作流脚本（15步）
├── workflow.json                # 工作流配置
├── mcp_server/
│   ├── server.py               # MCP Server（15个工具）
│   └── tools/
│       ├── data_tools.py       # Webhook/Airtable/CV下载（模拟）
│       ├── ai_tools.py         # CV提取/资质评估/邮件生成（GPT）
│       ├── filter_tools.py     # 候选人筛选
│       ├── calendar_tools.py   # 面试日历（模拟）
│       ├── notification_tools.py # 邮件/Slack/Webhook响应（模拟）
│       └── utils/
│           └── log_decorator.py
├── tests/
│   └── test_tools.py           # 单元测试
├── logs/
└── results/outputs/
```
