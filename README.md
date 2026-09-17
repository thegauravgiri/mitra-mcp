# Mitra MCP Server

Mitra is a modular Model Context Protocol (MCP) server that integrates Clockify, WakaTime, Azure DevOps, Jira, Google Calendar, and Notion. It enables developers and local AI assistants to fetch active projects, manage Azure DevOps work items (cards) and Jira issues, log time entries directly to Clockify, and manage calendar events, using a unified workflow.

Credentials are never baked into the server. There are two ways to supply them, depending on how the server is run:

- **Local (stdio) mode** — the server reads credentials straight from your shell environment. Nothing is persisted.
- **Remote (SSE/HTTP) mode** — the server runs a hosted **key vault**: each user signs in once with Google at `/vault`, stores their per-service API keys through a web UI, and those keys are encrypted at rest (envelope encryption via Cloud KMS) in Postgres. MCP clients then authenticate to the server itself — via OAuth or a personal access token — and the vault resolves the right keys for that user on every request. No secrets ever go into client config files.

---

## Code Architecture

Mitra uses an **integration-per-folder** architecture with **auto-discovery**. Each integration is self-contained — its client, tools, prompts, and context live together in one folder:

```text
src/mitra/
├── __init__.py
├── server.py                  # FastMCP instance + auto-discovery (never needs editing)
├── cli.py                     # CLI entrypoint: stdio runner + SSE/HTTP app, auth middleware
│
├── core/                      # Shared infrastructure
│   ├── __init__.py
│   ├── context.py             # Base credential resolution helpers
│   ├── registry.py            # Auto-discovery engine
│   ├── auth_context.py        # Per-request "current user" ContextVar
│   ├── token_auth.py          # Bearer token validation (self-issued + Google ID tokens)
│   ├── authserver_routes.py   # Mitra-as-OAuth-authorization-server (DCR, /authorize, /token)
│   ├── authserver_store.py    # Postgres storage for OAuth clients/codes/refresh tokens
│   ├── pat_store.py           # Personal access tokens (hashed, header-auth fallback to OAuth)
│   ├── vault_service.py       # Key vault: envelope encryption + persistence entry point
│   ├── vault_store.py         # Postgres storage for encrypted per-user API keys
│   ├── vault_validators.py    # Validates a key against its provider before storing it
│   ├── kms_vault.py           # Cloud KMS-backed envelope encryption (wrap/unwrap DEKs)
│   ├── oauth_service.py       # Google Calendar OAuth credential service
│   ├── oauth_store.py         # Postgres storage for Calendar OAuth credentials
│   ├── crypto.py              # Symmetric encryption helpers
│   └── user.py                # User identity helpers
│
├── webapp/                    # Vault web UI (MVC): sign-in, key CRUD, PAT management, connect page
│   ├── __init__.py
│   ├── routes.py               # Controller: /vault, /vault/keys, /vault/tokens, /vault/connect
│   ├── service_config.py       # Model: per-service form fields (single source of truth)
│   ├── session.py              # Signed session cookie helpers
│   ├── templates/               # Jinja2 views (vault.html, tokens.html, connect.html, ...)
│   └── static/
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
    ├── jira/                  # Jira issues, comments, transitions
    │   ├── __init__.py
    │   ├── client.py
    │   ├── tools.py
    │   ├── prompts.py
    │   └── context.py
    │
    ├── google_calendar/       # Google Calendar events (OAuth-based, not header-based)
    │   ├── __init__.py
    │   ├── service.py
    │   └── tools.py
    │
    ├── notion/                # Notion Dashboard skill (prompt/resource only)
    │   ├── __init__.py
    │   └── prompts.py
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

Mitra can run in two modes: **local stdio** (per-developer, credentials from the shell) and **remote SSE/HTTP** (shared server, credentials from the vault). Most day-to-day users only need the remote mode — see the [Setup Guide](./SETUP_GUIDE.md) for client-side connection instructions if you're connecting to an existing hosted Mitra instance rather than running your own.

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


### 2. Remote SSE/HTTP Mode (For Hosted / Shared Deployments)

In remote mode, the server is hosted as an HTTP app and each user's credentials live in a server-side **key vault**, not in client config. This is what makes the server safe to share across a team from a single deployment.

#### Server configuration

Remote mode needs a few extra pieces of infrastructure beyond the stdio mode. Copy `.env_example` to `.env` and fill in:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string — backs the vault, PATs, and OAuth state |
| `KMS_KEY_RESOURCE_NAME` | Cloud KMS key used to wrap the per-user data keys that encrypt vaulted secrets |
| `SESSION_SECRET` | Signs the vault web UI's session cookie |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth app used for both vault sign-in and the MCP authorization flow |
| `GOOGLE_WEB_REDIRECT_URI` | Callback for signing into the vault web UI (`<host>/vault/callback`) |
| `GOOGLE_REDIRECT_URI` | Callback for the Google Calendar integration's own OAuth grant (`<host>/auth/google/callback`) |
| `MCP_JWT_SECRET` | Signs the short-lived access tokens Mitra issues to MCP clients after they complete OAuth |
| `MCP_RESOURCE_URI` | Canonical URI of this server's `/mcp` endpoint (defaults to `<request base url>/mcp`) |
| `ALLOWED_HOSTS` | Comma-separated allowed `Host` headers, or `*` |

Start the server:
```bash
mitra start --transport sse --host 127.0.0.1 --port 8000
```

#### How users connect their credentials (the vault)

1. A user signs in at `<server-url>/vault` with Google.
2. They add their per-service API keys (Clockify, WakaTime, Azure DevOps PAT + org URL, Jira token + email + site URL) through the web form. Each key is validated against its provider, then encrypted at rest with envelope encryption (Cloud KMS-wrapped data key) and stored in Postgres — plaintext keys never touch disk or logs.
3. Google Calendar is connected separately via its own one-time OAuth grant, either by running the `google_calendar_connect` tool or visiting `/auth/google/start` — this is unaffected by the vault above.

At request time, `vault_injection_middleware` (in `cli.py`) resolves the authenticated user's identity and injects their vaulted keys into the same context vars each integration already reads from — no code in the integrations themselves knows the vault exists.

#### How MCP clients authenticate to the server

Once a user's keys are in the vault, their MCP client needs to prove *who it is* — two ways:

- **OAuth (preferred)** — Mitra acts as its own OAuth 2.1 authorization server (Dynamic Client Registration + PKCE), so any spec-compliant client just needs the server URL: it discovers `/.well-known/oauth-protected-resource`, registers itself, and redirects the user through the same Google sign-in used for the vault. No client id, secret, or key ever goes into the client config.
- **Personal access token (fallback)** — for clients that can't do the OAuth dance, a user generates a token at `/vault/tokens` (shown once, stored only as a hash) and configures their client to send `Authorization: Bearer <token>`.

A legacy dual-mode also exists for clients still sending the old per-request headers (`X-Clockify-Api-Key`, `X-Azure-Devops-Pat`, etc.) directly and unauthenticated — this is a migration path only and is expected to be removed once all clients are on the vault.

See the [Setup Guide](./SETUP_GUIDE.md) for exact client configuration steps (VS Code, Claude Desktop, Claude Code, Codex).
