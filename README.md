# Mitra MCP Server

Mitra is a modular, stateless Model Context Protocol (MCP) server that integrates Clockify, WakaTime, and Azure DevOps. It enables developers and local AI assistants to fetch active projects, manage Azure DevOps work items (cards), and log time entries directly to Clockify using a unified workflow.

The server is fully **stateless**: individual team members supply their credentials (API keys, workspace IDs, Personal Access Tokens) via request headers (in remote/SSE mode) or local environment variables (in stdio mode).

---

## Code Architecture

Mitra is structured to be clean, modular, and extremely easy to extend:

```text
src/mitra/
├── __init__.py
├── server.py           # Initializes FastMCP and registers modules
├── cli.py              # Command-line interface to start the server
├── context.py          # Dynamic context variables and credential resolution helpers
├── clients/            # Pure stateless API clients for third-party integrations
│   ├── __init__.py
│   ├── clockify.py     # ClockifyClient
│   ├── wakatime.py     # WakaTimeClient
│   └── azure_devops.py # AzureDevOpsClient
├── tools/              # MCP tool registration functions
│   ├── __init__.py     # Hub to register all integration tools
│   ├── clockify.py     # Clockify tools registration
│   ├── wakatime.py     # WakaTime tools registration
│   ├── azure_devops.py # Azure DevOps tools registration
│   └── linkage.py      # Unified linkages (e.g. Clockify + Azure DevOps)
└── prompts/            # Agent prompts & system resources
    ├── __init__.py
    └── guides.py       # Unified instructions guides and rules
```

### Adding a New Integration (Developer Guide)

Adding a new integration (for example, `Jira` or `Github`) is simple:
1. **Create the Client**: Add `src/mitra/clients/jira.py` to wrap the Jira REST API.
2. **Create the Tools**: Add `src/mitra/tools/jira.py` and write a `register(mcp)` function defining Jira-specific tools using `@mcp.tool()`.
3. **Register the Tools**: Import and call the registration function in `src/mitra/tools/__init__.py`.

This design separates the client layer (external API requests) from the tool layer (MCP protocol schema and definitions), making the codebase easy to maintain.

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
