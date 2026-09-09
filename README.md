# Mitra MCP Server

Mitra is a modular, stateless Model Context Protocol (MCP) server that integrates Clockify, WakaTime, Azure DevOps, and Jira. It enables developers and local AI assistants to fetch active projects, manage Azure DevOps work items (cards) and Jira issues, and log time entries directly to Clockify using a unified workflow.

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
    ├── jira/                  # Jira issues
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

Adding a new integration (for example, `Github` or `Trello`) requires creating **one folder** — no other files need to be modified:

```bash
mkdir -p src/mitra/integrations/trello
```

**1. Create the entry point** (`__init__.py`):
```python
# src/mitra/integrations/trello/__init__.py
from mitra.integrations.trello.tools import register_tools

def register(mcp):
    register_tools(mcp)
```

**2. Create the API client** (`client.py`):
```python
# src/mitra/integrations/trello/client.py
class TrelloClient:
    def __init__(self, api_key: str): ...
    async def list_cards(self, board: str): ...
```

**3. Create the tools** (`tools.py`):
```python
# src/mitra/integrations/trello/tools.py
from mitra.integrations.trello.client import TrelloClient

def register_tools(mcp):
    @mcp.tool()
    async def trello_list_cards(board: str, api_key: str) -> list:
        """Lists Trello cards for a board."""
        client = TrelloClient(api_key)
        return await client.list_cards(board)
```

**4. (Optional) Add credential headers** (`context.py`):
```python
# src/mitra/integrations/trello/context.py
import contextvars
from mitra.core.context import resolve_credential

request_trello_api_key = contextvars.ContextVar("trello_api_key", default=None)

HEADERS = {"x-trello-api-key": request_trello_api_key}

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
export JIRA_EMAIL="your-atlassian-account-email"
export JIRA_API_TOKEN="your-jira-api-token"
export JIRA_URL="https://your-domain.atlassian.net"
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
        "AZURE_DEVOPS_ORG": "https://dev.azure.com/your-org",
        "JIRA_EMAIL": "your-atlassian-account-email",
        "JIRA_API_TOKEN": "your-jira-api-token",
        "JIRA_URL": "https://your-domain.atlassian.net"
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
  -e JIRA_EMAIL="your-atlassian-account-email" \
  -e JIRA_API_TOKEN="your-jira-api-token" \
  -e JIRA_URL="https://your-domain.atlassian.net" \
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
- `X-Jira-Email`
- `X-Jira-Api-Token`
- `X-Jira-Url`

Start the server:
```bash
mitra start --transport sse --host 127.0.0.1 --port 8000
```
