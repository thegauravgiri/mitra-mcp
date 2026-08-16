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
        import logging
        import os
        from fastapi import Request
        from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
        from mitra.core.registry import collect_headers
        from mitra.core import auth_context, token_auth
        from mitra.core.vault_service import get_vault_service

        logger = logging.getLogger("mitra.auth")

        click.echo(f"Starting Mitra MCP server in SSE mode on http://{host}:{port} ...", err=True)

        mcp_app = mcp.http_app() if hasattr(mcp, "http_app") else None

        @contextlib.asynccontextmanager
        async def lifespan(app: FastAPI):
            if hasattr(mcp, "session_manager"):
                async with mcp.session_manager.run():
                    yield
            elif mcp_app is not None and hasattr(mcp_app, "lifespan"):
                async with mcp_app.lifespan(app):
                    yield
            else:
                yield

        app = FastAPI(title="Mitra Remote MCP Server", lifespan=lifespan)

        # Enforce trusted hosts if ALLOWED_HOSTS is defined
        allowed_hosts_env = os.environ.get("ALLOWED_HOSTS")
        if allowed_hosts_env:
            from fastapi.middleware.trustedhost import TrustedHostMiddleware
            # Strip wrapping quotes from the env string
            allowed_hosts_env = allowed_hosts_env.strip("'\"")
            # Split by comma and strip quotes/whitespace from each host element
            allowed_hosts = [h.strip("'\" ").lower() for h in allowed_hosts_env.split(",") if h.strip()]
            
            # Starlette TrustedHostMiddleware uses ["*"] to allow all hosts
            if "*" in allowed_hosts:
                allowed_hosts = ["*"]
                
            app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

        # Add CORS middleware to allow cross-origin requests from remote & web MCP clients
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # ── Generic OAuth Endpoints ──────────────────────────────────────────────────

        @app.get("/auth/{provider}/start")
        async def oauth_start(request: Request, provider: str, user_id: str = None):
            provider_key = provider.lower()
            if provider_key != "google":
                return HTMLResponse(f"<h3>Unsupported provider: {provider}</h3>", status_code=400)

            # If the caller has a signed-in vault session, that identity always wins over
            # the query param — otherwise anyone could complete this flow for an arbitrary
            # user_id and have their own Google grant filed under someone else's identity.
            from mitra.webapp import session as vault_session
            session_cookie = request.cookies.get("mitra_session")
            session_user_id = vault_session.unsign(session_cookie) if session_cookie else None
            effective_user_id = session_user_id or user_id

            if not effective_user_id:
                return HTMLResponse(
                    "<h3>Sign in required</h3>"
                    "<p>Sign in at <a href='/vault/login'>/vault/login</a> first, "
                    "or provide a 'user_id' parameter.</p>",
                    status_code=400,
                )

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
            state = base64.urlsafe_b64encode(effective_user_id.encode()).decode()

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

        # ── OAuth authorization-server proxy (DCR + authorize + token) ─────────────────
        # Makes Mitra itself the OAuth authorization server from the MCP client's point
        # of view, so "connect" is just server URL -> Google consent screen -> done,
        # with no manual client id entry. See core/authserver_routes.py for why.
        from mitra.core.authserver_routes import router as authserver_router
        app.include_router(authserver_router)

        # ── Key vault web app (add / list / delete per-service API keys) ───────────────
        # MVC slice living in mitra.webapp: models in service_config.py, views as
        # Jinja2 templates, controller as this router. See mitra/webapp/__init__.py.
        from fastapi.staticfiles import StaticFiles
        import mitra.webapp as webapp_pkg
        from mitra.webapp.routes import router as vault_router
        from mitra.webapp.service_config import SERVICES as VAULT_SERVICE_CONFIG

        app.include_router(vault_router)
        app.mount(
            "/vault/static",
            StaticFiles(directory=os.path.join(os.path.dirname(webapp_pkg.__file__), "static")),
            name="vault-static",
        )

        # ── Credential resolution middleware stack ──────────────────────────────────
        # Auto-collect all header → ContextVar mappings from every integration
        header_mappings = collect_headers()

        # Derived from the same service_config.py the web app's form renders from,
        # so the vault, the form, and this injection step can't drift out of sync.
        VAULT_SERVICE_SECRET_HEADERS = {
            key: cfg.secret_header for key, cfg in VAULT_SERVICE_CONFIG.items()
        }
        VAULT_SERVICE_METADATA_HEADERS = {
            key: {f.name: f.header for f in cfg.extra_fields}
            for key, cfg in VAULT_SERVICE_CONFIG.items()
        }

        @app.middleware("http")
        async def vault_injection_middleware(request: Request, call_next):
            # Runs closer to the route than extract_headers_middleware below (see comment
            # there on Starlette's outer-to-inner ordering), so a vaulted key wins over a
            # stale legacy header from a client that hasn't fully migrated yet.
            user_id = auth_context.get_current_user_id()
            tokens = []
            if user_id:
                vault = get_vault_service()
                for service, header_name in VAULT_SERVICE_SECRET_HEADERS.items():
                    context_var = header_mappings.get(header_name)
                    if context_var is None:
                        continue
                    try:
                        result = await vault.get_key(user_id, service)
                    except Exception:
                        logger.exception("Vault lookup failed for user=%s service=%s", user_id, service)
                        result = None
                    if not result:
                        continue
                    tokens.append((context_var, context_var.set(result["secret"])))
                    for meta_key, meta_header in VAULT_SERVICE_METADATA_HEADERS.get(service, {}).items():
                        meta_var = header_mappings.get(meta_header)
                        meta_value = result["metadata"].get(meta_key)
                        if meta_var is not None and meta_value:
                            tokens.append((meta_var, meta_var.set(meta_value)))
            try:
                return await call_next(request)
            finally:
                for context_var, token in tokens:
                    context_var.reset(token)

        @app.middleware("http")
        async def extract_headers_middleware(request: Request, call_next):
            # Registered before vault_injection_middleware above, which makes this the
            # OUTER layer (Starlette runs the most-recently-added @app.middleware("http")
            # first) — so header extraction happens first, then vault injection can
            # override the same ContextVars afterwards.
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

        # ── OAuth 2.1 resource-server metadata (RFC 9728) ──────────────────────────────

        RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"
        PROTECTED_PATH_PREFIXES = ("/mcp", "/sse")

        def _resource_uri(request: Request) -> str:
            return os.environ.get("MCP_RESOURCE_URI") or str(request.base_url).rstrip("/") + "/mcp"

        @app.get(RESOURCE_METADATA_PATH)
        async def protected_resource_metadata(request: Request):
            return JSONResponse({
                "resource": _resource_uri(request),
                "authorization_servers": [str(request.base_url).rstrip("/")],
                "bearer_methods_supported": ["header"],
            })

        @app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            path = request.url.path
            if not path.startswith(PROTECTED_PATH_PREFIXES):
                return await call_next(request)

            auth_header = request.headers.get("authorization", "")
            scheme, _, token = auth_header.partition(" ")
            has_bearer = scheme.lower() == "bearer" and bool(token)
            has_legacy_headers = any(h in request.headers for h in header_mappings)

            if not has_bearer:
                if has_legacy_headers:
                    # Dual-mode: existing header-key clients keep working unauthenticated
                    # against the MCP transport until the vault ships (see migration plan).
                    return await call_next(request)
                metadata_url = str(request.base_url).rstrip("/") + RESOURCE_METADATA_PATH
                return JSONResponse(
                    {"error": "invalid_request", "error_description": "missing bearer token"},
                    status_code=401,
                    headers={"WWW-Authenticate": f'Bearer resource_metadata="{metadata_url}"'},
                )

            try:
                claims = token_auth.validate_bearer_token(token, resource_uri=_resource_uri(request))
            except token_auth.TokenValidationError as exc:
                logger.warning("Bearer token rejected: %s", exc)
                metadata_url = str(request.base_url).rstrip("/") + RESOURCE_METADATA_PATH
                return JSONResponse(
                    {"error": "invalid_token", "error_description": str(exc)},
                    status_code=401,
                    headers={
                        "WWW-Authenticate": (
                            f'Bearer resource_metadata="{metadata_url}", error="invalid_token"'
                        )
                    },
                )

            resolved_user_id = claims.get("email") or claims["sub"]
            logger.info("Authenticated MCP request for user %s", resolved_user_id)
            reset_token = auth_context.CURRENT_USER_ID.set(resolved_user_id)
            try:
                return await call_next(request)
            finally:
                auth_context.CURRENT_USER_ID.reset(reset_token)

        @app.get("/health")
        async def health():
            return {"status": "ok", "service": "mitra-mcp"}

        @app.get("/")
        async def root():
            return RedirectResponse(url="/mcp", status_code=307)

        if mcp_app is not None:
            app.mount("/", mcp_app)
            try:
                sse_subapp = mcp.http_app(transport="sse")
                app.mount("/sse", sse_subapp)
            except Exception:
                pass
        elif hasattr(mcp, "streamable_http_app"):
            app.mount("/", mcp.streamable_http_app())

        # Cloud Run terminates TLS at its edge and forwards plain HTTP with an
        # X-Forwarded-Proto header; without proxy_headers, request.base_url (used
        # throughout the OAuth metadata/authorize/callback URLs above) resolves as
        # http:// instead of https://, which Google's redirect_uri validation rejects.
        uvicorn.run(app, host=host, port=port, proxy_headers=True, forwarded_allow_ips="*")

if __name__ == "__main__":
    cli()

