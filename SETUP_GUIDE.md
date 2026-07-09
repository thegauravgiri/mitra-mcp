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
| `USER_ID` | (Optional) Your email address to identify your Google Calendar settings. Defaults to the email address retrieved from Clockify if omitted. |

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

## 3. Integrating with Claude Code (CLI)

If you are using the **Claude Code CLI**, you can register the Mitra MCP server using the `claude mcp add` command. 

Run the following command to add Mitra globally (using `--scope user`) or omit `--scope user` to configure it only for the current project:

```bash
claude mcp add mitra --scope user \
  -e CLOCKIFY_API_KEY="your_clockify_api_key" \
  -e CLOCKIFY_WORKSPACE_ID="your_workspace_id" \
  -e WAKATIME_API_KEY="your_wakatime_api_key" \
  -e AZURE_DEVOPS_PAT="your_azure_devops_pat" \
  -e AZURE_DEVOPS_ORG="https://dev.azure.com/your_organization" \
  -- /Users/gauravgiri/Developer/proshore/mitra/.venv/bin/mitra start --transport stdio
```

### Useful CLI Commands for Managing MCP:
- **List installed servers:** `claude mcp list`
- **Remove Mitra:** `claude mcp remove mitra`
- **Interactive session control:** Type `/mcp` inside the Claude Code chat session to view status and toggle connections.

---

## 4. Remote Hosting (SSE Mode)

When hosting the server remotely:

### 1. Server Configuration
Start the server in SSE mode. You must provide the following environment variables to support Google Calendar multi-user authentication:
- `GOOGLE_CLIENT_ID`: Your Google OAuth Client ID.
- `GOOGLE_CLIENT_SECRET`: Your Google OAuth Client Secret.
- `GOOGLE_REDIRECT_URI`: The callback endpoint (e.g., `https://mitra-server.com/auth/google/callback`).
- `GOOGLE_ENCRYPTION_KEY`: A 32-byte url-safe base64-encoded key for credential encryption (e.g., generated with `cryptography.fernet.Fernet.generate_key()`).

```bash
GOOGLE_CLIENT_ID="your_client_id" \
GOOGLE_CLIENT_SECRET="your_client_secret" \
GOOGLE_REDIRECT_URI="http://localhost:8000/auth/google/callback" \
GOOGLE_ENCRYPTION_KEY="your_base64_fernet_key" \
mitra start --transport sse --host 0.0.0.0 --port 8000
```

### 2. Client Authentication
Clients should configure connection credentials within HTTP headers sent along with client requests:
- `x-clockify-api-key`
- `x-clockify-workspace-id`
- `x-wakatime-api-key`
- `x-azure-devops-pat`
- `x-azure-devops-org`
- `x-user-id` (Optional: your email address to identify your Google Calendar settings; defaults to the email address retrieved from Clockify if omitted)

### 3. Connect Google Calendar (One-Time Setup)
To connect your Google Calendar:
1. Run the `google_calendar_connect` tool from your client/IDE, or navigate directly to `/auth/google/start?user_id=your_user_id` in your web browser.
2. Sign in with Google and authorize the app.
3. The server will securely save your encrypted tokens. You can now use all Google Calendar tools without sending access/refresh tokens in your headers!
