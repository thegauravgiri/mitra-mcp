import os

def load_dotenv():
    """Load environment variables from project root .env file if it exists."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dotenv_path = os.path.join(project_root, ".env")
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key not in os.environ:
                        os.environ[key] = val

# Load env variables immediately
load_dotenv()

import click
import uvicorn
from fastapi import FastAPI
from mitra.server import mcp

@click.group()
def cli():
    """Mitra CLI: Manage the Mitra MCP Server."""
    pass

@cli.command()
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio", "sse"]),
    help="Transport protocol to use (stdio for local IDEs, sse for remote/web services)."
)
@click.option("--host", default="127.0.0.1", help="Host address to bind the SSE server to.")
@click.option("--port", default=8000, type=int, help="Port to run the SSE server on.")
def start(transport, host, port):
    """Start the Mitra MCP Server."""
    if transport == "stdio":
        click.echo("Starting Mitra MCP server in stdio mode...", err=True)
        mcp.run(transport="stdio")
    else:
        import contextlib
        import os
        from fastapi import Request
        from fastapi.responses import RedirectResponse, HTMLResponse
        from mitra.core.registry import collect_headers

        click.echo(f"Starting Mitra MCP server in SSE mode on http://{host}:{port} ...", err=True)

        @contextlib.asynccontextmanager
        async def lifespan(app: FastAPI):
            async with mcp.session_manager.run():
                yield

        app = FastAPI(title="Mitra Remote MCP Server", lifespan=lifespan)

        # Enforce trusted hosts if ALLOWED_HOSTS is defined
        allowed_hosts_env = os.environ.get("ALLOWED_HOSTS")
        if allowed_hosts_env:
            from fastapi.middleware.trustedhost import TrustedHostMiddleware
            allowed_hosts = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]
            app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

        # ── Generic OAuth Endpoints ──────────────────────────────────────────────────

        @app.get("/auth/{provider}/start")
        async def oauth_start(provider: str, user_id: str):
            provider_key = provider.lower()
            if provider_key != "google":
                return HTMLResponse(f"<h3>Unsupported provider: {provider}</h3>", status_code=400)

            client_id = os.environ.get("GOOGLE_CLIENT_ID")
            redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")

            if not client_id or not redirect_uri:
                return HTMLResponse(
                    "<h3>Configuration Error</h3>"
                    "<p>GOOGLE_CLIENT_ID and GOOGLE_REDIRECT_URI must be configured on the server.</p>",
                    status_code=500
                )

            import urllib.parse
            scopes = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events"

            import base64
            state = base64.urlsafe_b64encode(user_id.encode()).decode()

            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={client_id}&"
                f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
                f"response_type=code&"
                f"scope={urllib.parse.quote(scopes)}&"
                f"access_type=offline&"
                f"prompt=consent&"
                f"state={state}"
            )
            return RedirectResponse(auth_url)

        @app.get("/auth/{provider}/callback")
        async def oauth_callback(provider: str, code: str, state: str):
            provider_key = provider.lower()
            if provider_key != "google":
                return HTMLResponse(f"<h3>Unsupported provider: {provider}</h3>", status_code=400)

            import base64
            try:
                user_id = base64.urlsafe_b64decode(state.encode()).decode()
            except Exception:
                return HTMLResponse("<h3>Error: Invalid state parameter.</h3>", status_code=400)

            client_id = os.environ.get("GOOGLE_CLIENT_ID")
            client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
            redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")

            if not client_id or not client_secret or not redirect_uri:
                return HTMLResponse("<h3>Configuration Error</h3><p>Server credentials configuration is incomplete.</p>", status_code=500)

            import httpx
            import datetime
            from datetime import timezone

            # Exchange code for tokens
            payload = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post("https://oauth2.googleapis.com/token", data=payload, timeout=10.0)
                if resp.status_code != 200:
                    return HTMLResponse(
                        f"<h3>Authorization Failed</h3><pre>{resp.text}</pre>",
                        status_code=400
                    )

                data = resp.json()
                access_token = data["access_token"]
                refresh_token = data.get("refresh_token")
                expires_in = data["expires_in"]

                if not refresh_token:
                    return HTMLResponse(
                        "<h3>Authorization Warning</h3>"
                        "<p>Google did not return a refresh token. "
                        "Please go to your <a href='https://myaccount.google.com/connections'>Google Account settings</a>, "
                        "remove 'Mitra', and try connecting again to enable permanent offline access.</p>",
                        status_code=400
                    )

                # Encrypt and save refresh token using CredentialService
                from mitra.core.oauth_service import get_credential_service
                service = get_credential_service()

                encrypted_refresh = service.encryption.encrypt(refresh_token)
                expires_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(seconds=expires_in)

                await service.store.save_credential(
                    user_id=user_id,
                    provider=provider_key,
                    access_token=access_token,
                    refresh_token=encrypted_refresh,
                    expires_at=expires_at,
                )

                html_content = """
                <html>
                <head>
                    <title>Mitra Authorization Successful</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                            background-color: #0f172a;
                            color: #f8fafc;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            min-height: 100vh;
                            margin: 0;
                        }
                        .card {
                            background-color: #1e293b;
                            border: 1px solid #334155;
                            border-radius: 12px;
                            padding: 2.5rem;
                            max-width: 500px;
                            width: 100%;
                            text-align: center;
                            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
                        }
                        h2 {
                            color: #38bdf8;
                            margin-top: 0;
                        }
                        p {
                            color: #94a3b8;
                            line-height: 1.6;
                        }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>Google Calendar Connected!</h2>
                        <p>Your credentials have been securely stored. You can now close this window and run the Google Calendar tools from your IDE client.</p>
                    </div>
                </body>
                </html>
                """
                return HTMLResponse(html_content)

        # Auto-collect all header → ContextVar mappings from every integration
        header_mappings = collect_headers()

        @app.middleware("http")
        async def extract_headers_middleware(request: Request, call_next):
            tokens = []
            for header_name, context_var in header_mappings.items():
                value = request.headers.get(header_name)
                if value:
                    token = context_var.set(value)
                    tokens.append((context_var, token))

            try:
                response = await call_next(request)
                return response
            finally:
                for context_var, token in tokens:
                    context_var.reset(token)

        app.mount("/", mcp.streamable_http_app())
        uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    cli()
