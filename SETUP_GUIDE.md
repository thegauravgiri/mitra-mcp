# Mitra MCP Server — Setup Guide

Mitra is hosted on a **shared remote server**. You do **not** need to install or run Mitra yourself — you only need to configure your IDE or AI client to connect to the remote instance. This guide covers how to do that.

> [!IMPORTANT]
> All connections to Mitra are **remote**. Your credentials (API keys, PATs) are sent as HTTP headers with every request and are never stored on the server.

---

## Prerequisites

Before you connect, gather the following credentials. You will enter them into your client's MCP configuration.

| Credential | Where to find it |
|---|---|
| **Clockify API Key** | [Clockify → Profile Settings → API](https://app.clockify.me/user/preferences#advanced) |
| **Clockify Workspace ID** | Clockify → Workspace Settings (the ID in the URL) |
| **WakaTime API Key** | [WakaTime → Settings → API Key](https://wakatime.com/settings/api-key) |
| **Azure DevOps PAT** | Azure DevOps → User Settings → Personal Access Tokens (needs `Work Items Read & Write`, `Project and Team Read` scopes) |
| **Azure DevOps Org URL** | Your organization URL, e.g. `https://dev.azure.com/your-organization` |
| **User ID** *(optional)* | Your email address, used to identify your Google Calendar account. If omitted, defaults to the email retrieved from your Clockify profile. |

You will also need the **Mitra server URL** from your administrator (e.g. `https://mitra.example.com`).

---

## Connecting from VS Code

VS Code supports remote MCP servers through the `mcp.json` settings file. You can configure it at the **user level** (applies to all workspaces) or the **workspace level**.

### User-level configuration

Create or edit the file at:
- **macOS / Linux**: `~/.config/Code/User/settings.json`  
- **Windows**: `%APPDATA%\Code\User\settings.json`

Add the following inside the top-level JSON object:

```json
{
  "mcp": {
    "servers": {
      "mitra": {
        "type": "sse",
        "url": "https://mitra.example.com/sse",
        "headers": {
          "x-clockify-api-key": "YOUR_CLOCKIFY_API_KEY",
          "x-clockify-workspace-id": "YOUR_CLOCKIFY_WORKSPACE_ID",
          "x-wakatime-api-key": "YOUR_WAKATIME_API_KEY",
          "x-azure-devops-pat": "YOUR_AZURE_DEVOPS_PAT",
          "x-azure-devops-org": "https://dev.azure.com/YOUR_ORGANIZATION",
          "x-user-id": "your.email@example.com"
        }
      }
    }
  }
}
```

### Workspace-level configuration

Create a `.vscode/mcp.json` file at the root of your project:

```json
{
  "servers": {
    "mitra": {
      "type": "sse",
      "url": "https://mitra.example.com/sse",
      "headers": {
        "x-clockify-api-key": "YOUR_CLOCKIFY_API_KEY",
        "x-clockify-workspace-id": "YOUR_CLOCKIFY_WORKSPACE_ID",
        "x-wakatime-api-key": "YOUR_WAKATIME_API_KEY",
        "x-azure-devops-pat": "YOUR_AZURE_DEVOPS_PAT",
        "x-azure-devops-org": "https://dev.azure.com/YOUR_ORGANIZATION",
        "x-user-id": "your.email@example.com"
      }
    }
  }
}
```

> [!TIP]
> You can use VS Code input variables to avoid hardcoding secrets. Replace any value with `"${input:variableName}"` and define the input in your workspace settings.

### Verify the connection

1. Open the **Command Palette** (`Cmd+Shift+P` / `Ctrl+Shift+P`).
2. Run **"MCP: List Servers"** — you should see `mitra` listed and connected.

---

## Connecting from Claude

Claude offers two interfaces — the **Claude Desktop** app and the **Claude Code** CLI. Both support remote MCP servers.

### Claude Desktop

Edit the Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add Mitra as a remote MCP server:

```json
{
  "mcpServers": {
    "mitra": {
      "url": "https://mitra.example.com/sse",
      "headers": {
        "x-clockify-api-key": "YOUR_CLOCKIFY_API_KEY",
        "x-clockify-workspace-id": "YOUR_CLOCKIFY_WORKSPACE_ID",
        "x-wakatime-api-key": "YOUR_WAKATIME_API_KEY",
        "x-azure-devops-pat": "YOUR_AZURE_DEVOPS_PAT",
        "x-azure-devops-org": "https://dev.azure.com/YOUR_ORGANIZATION",
        "x-user-id": "your.email@example.com"
      }
    }
  }
}
```

> [!NOTE]
> Unlike a local MCP server, there is no `command` or `args` field. You are connecting to a **remote** server — only `url` and `headers` are needed.

Restart Claude Desktop after saving the file.

### Claude Code (CLI)

Register Mitra as a remote MCP server using the `claude mcp add` command:

```bash
claude mcp add mitra \
  --transport sse \
  --scope user \
  --header "x-clockify-api-key: YOUR_CLOCKIFY_API_KEY" \
  --header "x-clockify-workspace-id: YOUR_CLOCKIFY_WORKSPACE_ID" \
  --header "x-wakatime-api-key: YOUR_WAKATIME_API_KEY" \
  --header "x-azure-devops-pat: YOUR_AZURE_DEVOPS_PAT" \
  --header "x-azure-devops-org: https://dev.azure.com/YOUR_ORGANIZATION" \
  --header "x-user-id: your.email@example.com" \
  --url https://mitra.example.com/sse
```

- Use `--scope user` to make Mitra available across all projects, or omit it for the current project only.
- Use `--scope project` to store the config in the current project's `.mcp.json`.

**Useful CLI commands:**

| Command | Description |
|---|---|
| `claude mcp list` | List all configured MCP servers |
| `claude mcp remove mitra` | Remove the Mitra server |
| `/mcp` (inside a session) | View status and toggle MCP connections |

---

## Connecting from Codex

OpenAI Codex CLI supports remote MCP servers through a configuration file.

Create or edit `~/.codex/config.json` (or the project-level `.codex/config.json`):

```json
{
  "mcpServers": {
    "mitra": {
      "type": "sse",
      "url": "https://mitra.example.com/sse",
      "headers": {
        "x-clockify-api-key": "YOUR_CLOCKIFY_API_KEY",
        "x-clockify-workspace-id": "YOUR_CLOCKIFY_WORKSPACE_ID",
        "x-wakatime-api-key": "YOUR_WAKATIME_API_KEY",
        "x-azure-devops-pat": "YOUR_AZURE_DEVOPS_PAT",
        "x-azure-devops-org": "https://dev.azure.com/YOUR_ORGANIZATION",
        "x-user-id": "your.email@example.com"
      }
    }
  }
}
```

Then start a Codex session as usual — Mitra tools will be available automatically.

---

## Google Calendar Setup (One-Time)

Google Calendar requires a one-time OAuth authorization. This is separate from the header-based credentials above.

1. **Initiate the connection** — do one of the following:
   - Ask your AI assistant to run the `google_calendar_connect` tool, **or**
   - Open this URL in your browser:  
     `https://mitra.example.com/auth/google/start?user_id=YOUR_EMAIL`
2. **Authorize with Google** — sign in and grant calendar access.
3. **Done** — the server securely stores your encrypted tokens. All Google Calendar tools will work automatically from this point on.

> [!NOTE]
> The `user_id` parameter should be the same email you use as your `x-user-id` header (or your Clockify email if you don't set that header).

---

## Credential Headers Reference

Every request to the remote Mitra server carries your credentials as HTTP headers. Your client sends these automatically once configured.

| Header | Required | Maps to |
|---|---|---|
| `x-clockify-api-key` | Yes | Clockify API Key |
| `x-clockify-workspace-id` | Yes | Clockify Workspace ID |
| `x-wakatime-api-key` | Yes | WakaTime API Key |
| `x-azure-devops-pat` | Yes | Azure DevOps Personal Access Token |
| `x-azure-devops-org` | Yes | Azure DevOps Organization URL |
| `x-user-id` | No | Your email (for Google Calendar identity; defaults to Clockify email) |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Tools not appearing | Verify the server URL is correct and reachable. Check that your client shows `mitra` as connected. |
| `401` or credential errors | Double-check that all required headers are set with valid API keys / PATs. |
| Google Calendar not working | Run the one-time OAuth flow described above. Ensure `x-user-id` matches the email you authorized with. |
| Connection timeouts | Confirm network access to the Mitra server. Check with your administrator if a VPN is required. |
