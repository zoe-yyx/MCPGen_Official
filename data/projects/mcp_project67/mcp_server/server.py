from fastmcp import FastMCP

from tools.data_tools import (
    receive_cv, store_candidate, get_job_requirements,
    download_cv, update_assessment, update_interview_details,
)
from tools.ai_tools import extract_cv_data, assess_qualification, generate_recruitment_email
from tools.filter_tools import filter_qualified, filter_interview
from tools.calendar_tools import schedule_interview
from tools.notification_tools import send_candidate_email, send_slack_notification, respond_webhook
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'RecruitmentPipeline'")

mcp = FastMCP("RecruitmentPipeline")

# Data tools
mcp.tool()(receive_cv)
mcp.tool()(store_candidate)
mcp.tool()(get_job_requirements)
mcp.tool()(download_cv)
mcp.tool()(update_assessment)
mcp.tool()(update_interview_details)

# AI tools
mcp.tool()(extract_cv_data)
mcp.tool()(assess_qualification)
mcp.tool()(generate_recruitment_email)

# Filter tools
mcp.tool()(filter_qualified)
mcp.tool()(filter_interview)

# Calendar tools
mcp.tool()(schedule_interview)

# Notification tools
mcp.tool()(send_candidate_email)
mcp.tool()(send_slack_notification)
mcp.tool()(respond_webhook)

logger.info("MCP server initialized with 15 tools registered.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
