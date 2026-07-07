# Mitra MCP Server

Mitra is a modular, stateless Model Context Protocol (MCP) server that integrates Clockify, WakaTime, and Azure DevOps. It enables developers and local AI assistants to fetch active projects, manage Azure DevOps work items (cards), and log time entries directly to Clockify using a unified workflow.

The server is fully **stateless**: individual team members supply their credentials (API keys, workspace IDs, Personal Access Tokens) via request headers (in remote/SSE mode) or local environment variables (in stdio mode).

---

## Code Architecture

Mitra uses an **integration-per-folder** architecture with **auto-discovery**. Each integration is self-contained — its client, tools, prompts, and context live together in one folder:

```text
src/mitra/
├── __init__.py
├── server.py                  # FastMCP instance + auto-discovery (never needs editing)
├── cli.py                     # CLI entrypoint (never needs editing)
│
├── core/                      # Shared infrastructure
│   ├── __init__.py
│   ├── context.py             # Base credential resolution helpers
│   └── registry.py            # Auto-discovery engine
│
└── integrations/              # ← Each integration is one self-contained folder
    ├── __init__.py
    │
    ├── clockify/              # Clockify time tracking
    │   ├── __init__.py        # register(mcp) entry point
    │   ├── client.py          # ClockifyClient (API wrapper)
    │   ├── tools.py           # @mcp.tool() definitions
    │   ├── prompts.py         # @mcp.prompt() + @mcp.resource()
    │   └── context.py         # Context vars, HTTP headers, resolvers
    │
    ├── wakatime/              # WakaTime coding activity
    │   ├── __init__.py
    │   ├── client.py
    │   ├── tools.py
    │   └── context.py
    │
    ├── azure_devops/          # Azure DevOps work items
    │   ├── __init__.py
    │   ├── client.py
    │   ├── tools.py
    │   ├── prompts.py
    │   └── context.py
    │
    └── workflows/             # Cross-integration composite tools
        ├── __init__.py
        ├── linkage.py         # Clockify ↔ Azure DevOps linkage
        ├── fill_clockify.py   # Composite fill-timesheet tools
        └── prompts.py         # Unified Mitra agent guide
```

### Adding a New Integration (Developer Guide)

Adding a new integration (for example, `Jira` or `Github`) requires creating **one folder** — no other files need to be modified:

```bash
mkdir -p src/mitra/integrations/jira
```

**1. Create the entry point** (`__init__.py`):
```python
# src/mitra/integrations/jira/__init__.py
from mitra.integrations.jira.tools import register_tools

def register(mcp):
    register_tools(mcp)
```

**2. Create the API client** (`client.py`):
```python
# src/mitra/integrations/jira/client.py
class JiraClient:
    def __init__(self, api_key: str): ...
    async def list_issues(self, project: str): ...
```

**3. Create the tools** (`tools.py`):
```python
# src/mitra/integrations/jira/tools.py
from mitra.integrations.jira.client import JiraClient

def register_tools(mcp):
    @mcp.tool()
    async def jira_list_issues(project: str, api_key: str) -> list:
        """Lists Jira issues for a project."""
        client = JiraClient(api_key)
        return await client.list_issues(project)
```

**4. (Optional) Add credential headers** (`context.py`):
```python
# src/mitra/integrations/jira/context.py
import contextvars
from mitra.core.context import resolve_credential

request_jira_api_key = contextvars.ContextVar("jira_api_key", default=None)

HEADERS = {"x-jira-api-key": request_jira_api_key}

def get_jira_api_key():
    return resolve_credential(request_jira_api_key, "JIRA_API_KEY")
```

**That's it.** The auto-discovery engine picks up your new folder automatically. The SSE middleware auto-collects your headers. No other files to touch.

---

## Installation

Clone the repository and install in editable mode:
```bash
pip install -e .
```

---

## Usage

### 1. Local stdio Mode (For Local IDEs / Claude Desktop)

In this mode, the server reads credentials directly from the shell environment.

Set the required environment variables:
```bash
export CLOCKIFY_API_KEY="your-clockify-api-key"
export CLOCKIFY_WORKSPACE_ID="your-clockify-workspace-id"
export WAKATIME_API_KEY="your-wakatime-api-key"
export AZURE_DEVOPS_PAT="your-azure-devops-pat"
export AZURE_DEVOPS_ORG="https://dev.azure.com/your-org"
```

Start the server:
```bash
mitra start --transport stdio
```

#### Claude Desktop Integration

To use Mitra locally with the Claude Desktop app, configure the server in your Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the following JSON snippet under the `mcpServers` key:

```json
{
  "mcpServers": {
    "mitra": {
      "command": "/absolute/path/to/your/venv/bin/mitra",
      "args": [
        "start",
        "--transport",
        "stdio"
      ],
      "env": {
        "CLOCKIFY_API_KEY": "your-clockify-api-key",
        "CLOCKIFY_WORKSPACE_ID": "your-clockify-workspace-id",
        "WAKATIME_API_KEY": "your-wakatime-api-key",
        "AZURE_DEVOPS_PAT": "your-azure-devops-pat",
        "AZURE_DEVOPS_ORG": "https://dev.azure.com/your-org"
      }
    }
  }
}
```

> [!NOTE]
> Make sure to replace `/absolute/path/to/your/venv/bin/mitra` with the actual path to the `mitra` executable inside your Python virtual environment (e.g., `which mitra`).


#### Claude Code (CLI) Integration

To use Mitra with the **Claude Code CLI**, register it using the `claude mcp add` command. 

Run the following command in your terminal to configure the server (add the `--scope user` flag if you want it to be globally available across all projects):

```bash
claude mcp add mitra --scope user \
  -e CLOCKIFY_API_KEY="your-clockify-api-key" \
  -e CLOCKIFY_WORKSPACE_ID="your-clockify-workspace-id" \
  -e WAKATIME_API_KEY="your-wakatime-api-key" \
  -e AZURE_DEVOPS_PAT="your-azure-devops-pat" \
  -e AZURE_DEVOPS_ORG="https://dev.azure.com/your-org" \
  -- /absolute/path/to/your/venv/bin/mitra start --transport stdio
```

You can view active servers by typing `/mcp` inside your Claude Code session, or check the list using `claude mcp list`.


### 2. Remote SSE Mode (For Web Services)

In remote mode, the server is hosted as an HTTP app. Clients supply credentials on a per-request basis using HTTP headers:
- `X-Clockify-Api-Key`
- `X-Clockify-Workspace-Id`
- `X-Wakatime-Api-Key`
- `X-Azure-Devops-Pat`
- `X-Azure-Devops-Org`

Start the server:
```bash
mitra start --transport sse --host 127.0.0.1 --port 8000
```
