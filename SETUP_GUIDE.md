# Mitra MCP Server Setup & Team Integration Guide

This guide explains how to host the Mitra MCP server as a shared, remote service and how individual team members can connect their local Copilots / Agents (e.g., GitHub Copilot, Cline, Roo-Code) using their own separate Clockify environments.

---

## 1. Hosting the Server (Centrally)

To run the Mitra MCP server on a remote server for your team:

1. **Configure credentials (if running in default local/global mode)**:
   If the server is meant to use a single set of shared credentials, you can configure it interactively before starting:
   ```bash
   mitra setup
   ```
   *(Note: If individual developers connect via SSE mode using their own custom headers in their clients as described in Section 2, the server itself does not need a local setup).*

2. **Deploy the server** using SSE (Server-Sent Events) mode.
   ```bash
   mitra start --transport sse --host 0.0.0.0 --port 8000
   ```

2. **Ensure port 8000 (or your configured port) is reachable** by your team members over the network.

---

## 2. Client Setup (For Teammates using Copilots / Agents)

Each team member has a local Copilot / Agent. They can connect to the remote server and configure their personal Clockify credentials (API key and Workspace ID) and WakaTime API Key via the client's `inputs` prompt system. 

The Project ID **does not need to be configured upfront**. The agent will read the server instructions, ask you dynamically during your first tracking request, and cache/remember it from history for subsequent updates.

### A. Configuring the Copilot / Agent (`mcp.json` / `settings.json`)
Add the following configuration to your client's MCP configuration file (typically `mcp.json` or within your Copilot agent's settings):

```json
{
  "servers": {
    "mitra": {
      "type": "http",
      "url": "http://<YOUR_SHARED_SERVER_IP>:8000/mcp",
      "headers": {
        "X-Clockify-Api-Key": "${input:clockifyApiKey}",
        "X-Clockify-Workspace-Id": "${input:clockifyWorkspaceId}",
        "X-Wakatime-Api-Key": "${input:wakatimeApiKey}"
      }
    }
  },
  "inputs": [
    {
      "id": "clockifyApiKey",
      "type": "promptString",
      "description": "Enter your Clockify API Key",
      "password": true
    },
    {
      "id": "clockifyWorkspaceId",
      "type": "promptString",
      "description": "Enter your Clockify Workspace ID"
    },
    {
      "id": "wakatimeApiKey",
      "type": "promptString",
      "description": "Enter your WakaTime API Key",
      "password": true
    }
  ]
}
```


### B. Alternative Client Settings (e.g., Cline / Roo-Code)
If your agent client uses a direct `mcpServers` format in settings:
```json
{
  "mcpServers": {
    "mitra": {
      "type": "sse",
      "url": "http://<YOUR_SHARED_SERVER_IP>:8000/mcp",
      "headers": {
        "X-Clockify-Api-Key": "YOUR_PERSONAL_CLOCKIFY_API_KEY",
        "X-Clockify-Workspace-Id": "YOUR_PERSONAL_WORKSPACE_ID",
        "X-Wakatime-Api-Key": "YOUR_PERSONAL_WAKATIME_API_KEY"
      }
    }
  }
}
```


### C. Agent Prompt & Instructions Resource
The Mitra MCP server publishes a prompt and a resource that your Copilot/Agent should read. These guidelines instruct the AI Agent to:
1. **Dynamic Project Discovery & Caching**: List workspace projects (`clockify_list_projects`) and interactively ask the developer which project to log to. The agent then caches this mapping in its context history to avoid asking again.
2. **Batch Logging**: Group and submit multiple pending entries or tracked durations at once, instead of logging single items one-by-one, minimizing turn times.
3. **Speed Optimization**: Retrieve coding time for files automatically using the server's WakaTime tools and avoid redundant tool calls.

*You can instruct your agent to read the prompt `clockify_agent_guide` or open the resource `instructions://clockify-rules` to ensure it follows these behaviors.*

---

## 3. Local Requirements (What Teammates Should Install)

To allow the Copilot / Agent to extract file information, git diffs, and logs, the teammate's **local machine** should have:

1. **Git CLI**:
   - Why: The Copilot agent runs locally in the developer's workspace and will execute local git commands (like `git diff`, `git status`, `git log`) to extract changed files, lines, and staging details.
   - Installation:
     - **macOS**: `brew install git`
     - **Windows**: Install [Git for Windows](https://git-scm.com/download/win)
     - **Linux**: `sudo apt install git` (or equivalent package manager)

2. **VS Code / Agent Extension**:
   - Why: This is the client agent that acts on behalf of the developer. It reads local files and sends summaries or calls the remote Clockify tools.
   - Recommended: **GitHub Copilot Chat**, **Cline**, or **Roo-Code**.

3. **WakaTime Extension (Optional)**:
   - Why: WakaTime automatically tracks how long you spend inside each file. The Mitra MCP server provides tools (`wakatime_get_today_projects` and `wakatime_get_today_file_durations`) to fetch this tracked time automatically from your local `~/.wakatime.cfg` API configuration.
   - Installation: Search for `WakaTime` in the Extensions Marketplace.

---

## 4. Workflow Example

1. Teammate edits [mitra/server.py](file:///Users/gauravgiri/Developer/proshore/mitra/src/mitra/server.py).
2. The Copilot / Agent queries the Mitra MCP server using `wakatime_get_today_file_durations(project="mitra")` to fetch the exact file path and total seconds coded in that file.
3. The Copilot / Agent uses the returned WakaTime seconds directly as the duration for the Clockify entry.
4. The Copilot / Agent invokes the remote MCP tool `clockify_add_time_entry` with a description and duration.
5. The remote MCP server receives the tool request accompanied by the user's custom `X-Clockify-Api-Key` headers, and automatically logs the entry into the user's personal Clockify account.


