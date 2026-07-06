# Mitra MCP Server Setup Guide

This guide walks you through configuring credentials and connecting the Mitra MCP server to local IDEs or remote web services.

---

## 1. Environment Variables Configuration

In **stdio** mode, Mitra reads settings directly from your system environment variables. You can add the following to your shell profile (`~/.zshrc` or `~/.bashrc`) or specify them when starting the server:

| Environment Variable | Description |
|---|---|
| `CLOCKIFY_API_KEY` | Your personal Clockify API Key (from Clockify Settings > Preferences). |
| `CLOCKIFY_WORKSPACE_ID` | The ID of your Clockify workspace to log time to. |
| `WAKATIME_API_KEY` | Your WakaTime API Key. |
| `AZURE_DEVOPS_PAT` | Personal Access Token (PAT) with `Work Items (Read & Write)` and `Project and Team (Read)` scopes. |
| `AZURE_DEVOPS_ORG` | Organization URL (e.g. `https://dev.azure.com/your-organization`). |

---

## 2. Integrating with Claude Desktop

To use Mitra locally with the Claude Desktop app, add the server to your Claude Desktop configuration file:

### Configuration File Path:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### Configuration Content:
```json
{
  "mcpServers": {
    "mitra": {
      "command": "/Users/gauravgiri/Developer/proshore/mitra/.venv/bin/mitra",
      "args": [
        "start",
        "--transport",
        "stdio"
      ],
      "env": {
        "CLOCKIFY_API_KEY": "your_clockify_api_key",
        "CLOCKIFY_WORKSPACE_ID": "your_workspace_id",
        "WAKATIME_API_KEY": "your_wakatime_api_key",
        "AZURE_DEVOPS_PAT": "your_azure_devops_pat",
        "AZURE_DEVOPS_ORG": "https://dev.azure.com/your_organization"
      }
    }
  }
}
```

Make sure to replace `/Users/gauravgiri/Developer/proshore/mitra/.venv/bin/mitra` with the actual path to the `mitra` executable in your virtual environment.

---

## 3. Remote Hosting (SSE Mode)

When hosting the server remotely:
1. Start the server using SSE transport:
   ```bash
   mitra start --transport sse --host 0.0.0.0 --port 8000
   ```
2. Clients should configure connection credentials within HTTP headers sent along with client requests:
   - `x-clockify-api-key`
   - `x-clockify-workspace-id`
   - `x-wakatime-api-key`
   - `x-azure-devops-pat`
   - `x-azure-devops-org`
