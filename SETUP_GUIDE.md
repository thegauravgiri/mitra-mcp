# Mitra MCP Server — Setup Guide

Mitra is hosted on a **shared remote server**. You do **not** need to install or run Mitra yourself — you only need to (1) put your credentials into Mitra's web vault once, and (2) point your IDE or AI client at the server. This guide covers both.

> [!IMPORTANT]
> Your credentials (API keys, PATs) are entered once into Mitra's **web vault**, where they're encrypted at rest and never leave the server. Your MCP client itself never holds your third-party API keys — it only needs to authenticate as *you*, via OAuth sign-in or a personal access token.

You will need the **Mitra server URL** from your administrator (e.g. `https://mitra.example.com`).

---

## Step 1: Add your credentials to the vault

1. Open `https://mitra.example.com/vault` in your browser and sign in with your Google account.
2. For each service you use, click **Add key** and fill in the form:

   | Service | What you'll be asked for | Where to find it |
   |---|---|---|
   | **Clockify** | API key, Workspace ID *(optional)* | [Clockify → Profile Settings → API](https://app.clockify.me/user/preferences#advanced) |
   | **WakaTime** | API key | [WakaTime → Settings → API Key](https://wakatime.com/settings/api-key) |
   | **Azure DevOps** | Personal access token, Organization URL | Azure DevOps → User Settings → Personal Access Tokens (needs `Work Items Read & Write`, `Project and Team Read` scopes) |
   | **Jira** | API token, Atlassian account email, Site URL | [Atlassian → Account Settings → Security → API tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |

3. Each key is validated against its provider before it's saved, then encrypted and stored — you'll see it listed with just its last 4 characters from then on.
4. **Google Calendar** is connected separately (it's an OAuth grant, not an API key) — see [Google Calendar Setup](#google-calendar-setup-one-time) below.

You only need to do this once. Come back to `/vault` any time to add, rotate, or delete a key.

---

## Step 2: Connect your MCP client

Once your keys are in the vault, your client needs to authenticate as you. There are two ways to do that — pick OAuth if your client supports it.

### Option A — OAuth sign-in (preferred)

Any MCP client that supports the MCP authorization spec only needs the server's `/mcp` URL — it discovers everything else (registration, sign-in) automatically and will pop up a Google sign-in prompt the first time it connects. Use the **same Google account** you used to sign into the vault.

- **Claude Desktop / Claude Code / VS Code / other OAuth-aware clients**: add the server as
  ```json
  {
    "mcpServers": {
      "mitra": {
        "url": "https://mitra.example.com/mcp"
      }
    }
  }
  ```
  (For Claude Code, `claude mcp add mitra --url https://mitra.example.com/mcp`.) The client will open a browser window to complete Google sign-in the first time it connects.

### Option B — Personal access token (for clients without OAuth support)

1. Go to `https://mitra.example.com/vault/tokens` and click **Generate token**. The raw token is shown **once** — copy it now.
2. Configure your client to send it as a bearer header:

   **VS Code** (`~/.config/Code/User/settings.json` or workspace `.vscode/mcp.json`):
   ```json
   {
     "mcp": {
       "servers": {
         "mitra": {
           "type": "sse",
           "url": "https://mitra.example.com/mcp",
           "headers": { "Authorization": "Bearer YOUR_MITRA_TOKEN" }
         }
       }
     }
   }
   ```

   **Claude Desktop / Claude Code / Codex** (any client that accepts a raw `headers` map):
   ```json
   {
     "mcpServers": {
       "mitra": {
         "url": "https://mitra.example.com/mcp",
         "headers": { "Authorization": "Bearer YOUR_MITRA_TOKEN" }
       }
     }
   }
   ```

   For Claude Code's CLI form: `claude mcp add mitra --url https://mitra.example.com/mcp --header "Authorization: Bearer YOUR_MITRA_TOKEN"`.

3. Revoke a token any time from `/vault/tokens` — it stops working immediately.

> [!TIP]
> `https://mitra.example.com/vault/connect` (once signed in) shows this same information pre-filled with your server's exact URLs.

### Verify the connection

- **VS Code**: Command Palette → **"MCP: List Servers"** — `mitra` should show as connected.
- **Claude Code**: `claude mcp list`, or `/mcp` inside a session.
- **Claude Desktop**: restart the app after saving config; check the MCP icon in a chat.

---

## Google Calendar Setup (One-Time)

Google Calendar uses its own OAuth grant, separate from the vault keys and from client sign-in above.

1. **Initiate the connection** — do one of the following:
   - Ask your AI assistant to run the `google_calendar_connect` tool, **or**
   - Open this URL in your browser:
     `https://mitra.example.com/auth/google/start?user_id=YOUR_EMAIL`
     (if you're already signed into the vault in that browser, `user_id` is optional — your vault identity is used automatically)
2. **Authorize with Google** — sign in and grant calendar access.
3. **Done** — the server securely stores your encrypted tokens. All Google Calendar tools will work automatically from this point on. You can disconnect it any time from `/vault`.

---

## Legacy: raw header-based credentials

Older client configs may still send credentials directly as request headers (`x-clockify-api-key`, `x-azure-devops-pat`, `x-jira-api-token`, etc.) instead of using the vault. The server still accepts this for backward compatibility, but it means secrets live in your client's config file and bypass the vault entirely — **migrate to Step 1 + Step 2 above** when you can. This fallback path is expected to be removed once all clients have migrated.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Tools not appearing | Verify the server URL is correct and reachable. Check that your client shows `mitra` as connected. |
| Client keeps prompting to sign in | Make sure you're completing the Google sign-in popup/browser tab it opens — some clients need pop-ups allowed for the server's domain. |
| `401 invalid_token` or credential errors | Your OAuth session or personal access token may have expired/been revoked — reconnect via Step 2, or generate a fresh token at `/vault/tokens`. |
| A tool says a key is missing | Check `/vault` — that service's key may not be added yet, or may have failed validation when you saved it. |
| Google Calendar not working | Run the one-time OAuth flow above, and check `/vault` shows it as connected. |
| Connection timeouts | Confirm network access to the Mitra server. Check with your administrator if a VPN is required. |
