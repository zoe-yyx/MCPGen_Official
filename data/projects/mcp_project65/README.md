# Smart Trade Alert Dispatcher for Slack & Telegram

MCP项目，将n8n工作流转换为基于FastMCP的Python项目。监控Apple股票(AAPL)的RSI指标和价格数据，使用GPT生成市场分析摘要，并根据优先级将警报路由到Telegram（高优先级）或Slack（低/中优先级）。

## 工作流程

1. **Fetch RSI Indicator** - 获取RSI技术指标数据（模拟TwelveData API）
2. **Fetch Price & Volume Data** - 获取价格和成交量数据（模拟TwelveData API）
3. **Merge API Responses** - 合并两个API的响应数据
4. **Calculate Trading Signals** - 计算交易信号（动量分类、成交量信号、操作建议）
5. **Generate AI Summary** - 使用GPT生成专业市场分析摘要
6. **Assign Alert Priority** - 根据RSI和成交量分配警报优先级
7. **Route by Priority** - 根据优先级路由到不同渠道
8. **Send to Telegram** - 高优先级警报发送到Telegram（模拟）
9. **Send to Slack** - 低/中优先级警报发送到Slack（模拟）

## 注意事项

- TwelveData API、Telegram、Slack、Gmail均为**Mock模式**，数据存储在本地`results/outputs/`目录
- OpenAI API为**真实调用**，使用gpt-5.1模型
- RSI和价格数据为随机生成的模拟数据

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

运行日志输出到`logs/workflow.log`，警报结果保存到`results/outputs/`。

## 运行测试

```bash
uv run python -m pytest tests/test_tools.py -v
```

## 项目结构

```
mcp_project65/
├── README.md
├── .env / .env.template
├── pyproject.toml
├── run_workflow.py              # 主工作流脚本
├── workflow.json                # 工作流配置
├── mcp_server/
│   ├── server.py               # MCP Server启动入口
│   └── tools/
│       ├── data_tools.py       # 数据采集工具
│       ├── signal_tools.py     # 信号处理工具
│       ├── ai_tools.py         # AI分析工具
│       ├── notification_tools.py # 通知工具
│       └── utils/
│           └── log_decorator.py # 日志装饰器
├── tests/
│   └── test_tools.py           # 单元测试
├── logs/                       # 日志目录
│   ├── server.log
│   └── workflow.log
└── results/
    └── outputs/                # 警报输出文件
```
