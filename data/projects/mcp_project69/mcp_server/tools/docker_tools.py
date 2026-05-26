"""Docker tools: SSH-based Docker operations (mocked with realistic sample output).

Simulates the SSH nodes: get logs, restart container, docker ps, update docker.
"""

import json
import uuid
from datetime import datetime, timezone

from .utils.log_decorator import log_mcp_call

# Mock log outputs per service
MOCK_LOGS: dict[str, str] = {
    "nginx": (
        "2026-04-23T05:00:01.123Z [notice] nginx/1.25.3\n"
        "2026-04-23T05:00:01.124Z [notice] built by gcc 12.2.0\n"
        "2026-04-23T05:00:01.125Z [notice] start worker processes\n"
        "2026-04-23T05:10:22.001Z [error] 1234#0: *5 connect() failed (111: Connection refused) "
        "while connecting to upstream, client: 10.0.0.5, upstream: \"ENDPOINT_PLACEHOLDER"\n"
        "2026-04-23T05:10:22.002Z [warn] 1234#0: *5 upstream server temporarily disabled\n"
        "2026-04-23T05:10:25.333Z [error] recv() failed (104: Connection reset by peer) "
        "while reading response header from upstream\n"
        "2026-04-23T05:15:00.001Z [notice] signal process started\n"
        "2026-04-23T05:15:00.512Z [error] open() \"/var/run/nginx.pid\" failed (2: No such file or directory)\n"
    ),
    "postgres": (
        "2026-04-23T04:00:00.001Z LOG:  database system was shut down at 2026-04-23 03:59:59 UTC\n"
        "2026-04-23T04:00:00.100Z LOG:  entering standby mode\n"
        "2026-04-23T04:00:00.200Z LOG:  redo starts at 0/3000028\n"
        "2026-04-23T04:55:12.001Z ERROR:  could not connect to the primary server: "
        "connection to server at \"primary\" (10.0.0.2), port 5432 failed: "
        "FATAL:  role \"replicator\" does not exist\n"
        "2026-04-23T04:55:12.002Z LOG:  replication terminated by primary server\n"
        "2026-04-23T04:55:12.003Z FATAL:  could not connect to the primary server\n"
    ),
    "redis": (
        "1:M 23 Apr 2026 05:00:00.001 # oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo\n"
        "1:M 23 Apr 2026 05:00:00.002 * monotonic clock: POSIX clock_gettime\n"
        "1:M 23 Apr 2026 05:00:00.050 * Running mode=standalone, port=6379.\n"
        "1:M 23 Apr 2026 05:01:15.001 # WARNING: 32 bytes blksize is too small\n"
        "1:M 23 Apr 2026 05:01:15.002 # Can't save in background: fork: Cannot allocate memory\n"
        "1:M 23 Apr 2026 05:01:15.003 * 1 changes in 3600 seconds. Saving...\n"
        "1:M 23 Apr 2026 05:01:15.100 # Background saving error\n"
    ),
}

MOCK_DOCKER_PS = (
    "<pre>NAMES\tSTATUS\n"
    "nginx\tUp 2 hours\n"
    "postgres\tUp 2 hours\n"
    "redis\tUp 45 minutes (unhealthy)\n"
    "app-backend\tUp 2 hours\n"
    "app-frontend\tExited (1) 5 minutes ago\n"
    "</pre>"
)

MOCK_UPDATE_STDOUT = (
    "Skipping n8n-compose.yaml (n8n instance)\n"
    "Processing nginx-compose.yaml\n"
    "Downloaded newer image for nginx:latest\n"
    "Processing postgres-compose.yaml\n"
    "Image is up to date for postgres:15\n"
    "Processing redis-compose.yaml\n"
    "Downloaded newer image for redis:7\n"
    "Update Summary:\n"
    '{"nginx-compose.yaml": ["nginx:latest: updated"], '
    '"postgres-compose.yaml": ["postgres:15: already up-to-date"], '
    '"redis-compose.yaml": ["redis:7: updated"]}'
)


@log_mcp_call("tool", "get_docker_logs")
def get_docker_logs(service_name: str, tail: int = 100) -> str:
    """Fetch last N log lines from a Docker container via SSH (mocked).

    Corresponds to 'docker logs --tail N <service>' SSH command.

    Args:
        service_name: Name of the Docker container.
        tail: Number of log lines to fetch (default 100).

    Returns:
        JSON string with 'stdout' and 'service_name' fields.
    """
    logs = MOCK_LOGS.get(service_name, (
        f"2026-04-23T05:00:00.000Z INFO  Container '{service_name}' started\n"
        f"2026-04-23T05:00:01.000Z INFO  Listening on port 8080\n"
        f"2026-04-23T05:05:00.000Z WARN  High memory usage detected: 87%\n"
        f"2026-04-23T05:05:01.000Z ERROR Connection timeout to dependency service\n"
    ))
    return json.dumps({"stdout": logs, "stderr": "", "service_name": service_name})


@log_mcp_call("tool", "restart_docker_container")
def restart_docker_container(service_name: str) -> str:
    """Restart a Docker container via SSH (mocked).

    Corresponds to 'docker restart <service>' SSH command.

    Args:
        service_name: Name of the Docker container to restart.

    Returns:
        JSON string with 'stdout', 'stderr', 'service_name'.
        Simulates success (empty stderr) by default.
    """
    if not service_name or service_name == "unknown":
        return json.dumps({
            "stdout": "",
            "stderr": f"Error: No such container: {service_name}",
            "service_name": service_name,
        })
    return json.dumps({
        "stdout": service_name,
        "stderr": "",
        "service_name": service_name,
    })


@log_mcp_call("tool", "check_restart_success")
def check_restart_success(restart_result: str) -> str:
    """Check whether Docker restart succeeded (stderr is empty).

    Corresponds to the If node checking stderr == empty.

    Args:
        restart_result: JSON string from restart_docker_container.

    Returns:
        JSON string with 'success' bool, 'stdout', 'stderr'.
    """
    data = json.loads(restart_result)
    stderr = data.get("stderr", "")
    success = not bool(stderr.strip())
    return json.dumps({
        "success": success,
        "stdout": data.get("stdout", ""),
        "stderr": stderr,
        "service_name": data.get("service_name", ""),
    })


@log_mcp_call("tool", "docker_ps")
def docker_ps() -> str:
    """List all running Docker containers via SSH (mocked).

    Corresponds to 'docker ps --format "{{.Names}}\\t{{.Status}}"' SSH command.

    Returns:
        JSON string with 'stdout' containing formatted container list.
    """
    return json.dumps({"stdout": MOCK_DOCKER_PS, "stderr": ""})


@log_mcp_call("tool", "run_docker_update")
def run_docker_update() -> str:
    """Run the update-all-docker-compose.sh script via SSH (mocked).

    Args: none.

    Returns:
        JSON string with 'stdout' containing the update script output.
    """
    return json.dumps({"stdout": MOCK_UPDATE_STDOUT, "stderr": ""})
