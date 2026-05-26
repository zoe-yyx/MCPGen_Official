# Google Calendar Interview Scheduler

MCP项目，将n8n工作流转换为基于FastMCP的Python项目。监控Google Sheets中的候选人信息，自动计算面试时间、创建日历事件、用GPT生成个性化邮件并发送。

## 工作流程

1. **Google Sheets Trigger** - 读取候选人数据（NAME, EMAIL, EDUCATIONAL）（模拟）
2. **Calculate Next Interview Slot** - 计算下一个可用面试时间（周一/三/五 下午3点）
3. **Create Google Calendar Event** - 创建1小时的日历事件（模拟）
4. **Generate Interview Email** - 使用GPT为每位候选人生成个性化面试邀请邮件
5. **Send Interview Email via Gmail** - 发送邮件给候选人（模拟）

## 注意事项

- Google Sheets、Google Calendar、Gmail均为**Mock模式**，数据存储在本地`results/outputs/`目录
- OpenAI API为**真实调用**，使用gpt-5.1模型
- 候选人数据为预设的模拟数据（3位候选人）
- 面试时间自动选择最近的周一/三/五下午3点（永远不选当天）

## 环境配置

1. 复制环境变量模板：
   ```bash
   cp .env.template .env
   ```

2. 编辑`.env`文件，填入API密钥：
   ```
   OPENAI_API_KEY=your-api-key
   OPENAI_BASE_URL=ENDPOINT_PLACEHOLDER
   MODEL=gpt-5.1
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

运行日志输出到`logs/workflow.log`，邮件结果保存到`results/outputs/`。

## 运行测试

```bash
uv run python -m pytest tests/test_tools.py -v
```

## 项目结构

```
mcp_project66/
├── README.md
├── .env / .env.template
├── pyproject.toml
├── run_workflow.py              # 主工作流脚本
├── workflow.json                # 工作流配置
├── mcp_server/
│   ├── server.py               # MCP Server启动入口
│   └── tools/
│       ├── sheets_tools.py     # Google Sheets模拟工具
│       ├── scheduling_tools.py # 时间计算与日历事件工具
│       ├── ai_tools.py         # GPT邮件生成工具
│       ├── email_tools.py      # Gmail模拟发送工具
│       └── utils/
│           └── log_decorator.py # 日志装饰器
├── tests/
│   └── test_tools.py           # 单元测试
├── logs/
│   ├── server.log
│   └── workflow.log
└── results/
    └── outputs/                # 邮件输出文件
```
