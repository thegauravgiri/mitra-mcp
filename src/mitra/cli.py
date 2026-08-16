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
        from fastapi import Form, Request
        from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
        from mitra.core.registry import collect_headers
        from mitra.core import auth_context, token_auth
        from mitra.core.vault_service import get_vault_service
        from mitra.core import vault_validators

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

        # ── Key vault web app (add / list / delete per-service API keys) ───────────────

        def _session_secret() -> str:
            secret = os.environ.get("SESSION_SECRET")
            if not secret:
                raise RuntimeError("SESSION_SECRET must be set to use the web vault UI")
            return secret

        def _sign(value: str) -> str:
            import hashlib
            import hmac
            mac = hmac.new(_session_secret().encode(), value.encode(), hashlib.sha256).hexdigest()
            return f"{value}.{mac}"

        def _unsign(signed: str):
            import hashlib
            import hmac
            if "." not in signed:
                return None
            value, _, mac = signed.rpartition(".")
            expected = hmac.new(_session_secret().encode(), value.encode(), hashlib.sha256).hexdigest()
            return value if hmac.compare_digest(mac, expected) else None

        def _require_session(request: Request):
            cookie = request.cookies.get("mitra_session")
            return _unsign(cookie) if cookie else None

        VAULT_SERVICES = ("clockify", "wakatime", "azure_devops")

        def _vault_page(user_id: str, keys, error: str = "") -> str:
            rows = "".join(
                f"<tr><td>{k['service']}</td><td>****{k['last4']}</td>"
                f"<td>{k.get('last_validated_at') or '—'}</td>"
                f"<td><form method='post' action='/vault/keys/{k['service']}/delete' style='display:inline'>"
                f"<button type='submit'>Delete</button></form></td></tr>"
                for k in keys
            )
            error_html = f"<p style='color:#b91c1c'>{error}</p>" if error else ""
            options = "".join(f"<option value='{s}'>{s}</option>" for s in VAULT_SERVICES)
            return f"""
            <html><head><title>Mitra Key Vault</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; max-width: 640px; margin: 3rem auto; }}
                table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
                td, th {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }}
                input, select {{ padding: 6px; margin: 4px 0; width: 100%; box-sizing: border-box; }}
            </style></head>
            <body>
                <h2>Mitra key vault</h2>
                <p>Signed in as {user_id} — <a href="/vault/logout">sign out</a></p>
                {error_html}
                <table>
                    <tr><th>Service</th><th>Key</th><th>Last validated</th><th></th></tr>
                    {rows or '<tr><td colspan="4">No keys connected yet.</td></tr>'}
                </table>
                <h3>Add a key</h3>
                <form method="post" action="/vault/keys">
                    <label>Service</label>
                    <select name="service">{options}</select>
                    <label>API key / PAT</label>
                    <input name="secret" type="password" required />
                    <label>Organization URL (Azure DevOps only)</label>
                    <input name="organization_url" placeholder="https://dev.azure.com/your-org" />
                    <button type="submit">Save</button>
                </form>
            </body></html>
            """

        @app.get("/vault/login")
        async def vault_login():
            client_id = os.environ.get("GOOGLE_CLIENT_ID")
            web_redirect_uri = os.environ.get("GOOGLE_WEB_REDIRECT_URI")
            if not client_id or not web_redirect_uri:
                return HTMLResponse(
                    "<h3>Configuration Error</h3>"
                    "<p>GOOGLE_CLIENT_ID and GOOGLE_WEB_REDIRECT_URI must be configured.</p>",
                    status_code=500,
                )
            import secrets as secrets_mod
            import urllib.parse
            state = secrets_mod.token_urlsafe(24)
            auth_url = (
                "https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={client_id}&"
                f"redirect_uri={urllib.parse.quote(web_redirect_uri)}&"
                "response_type=code&"
                f"scope={urllib.parse.quote('openid email')}&"
                f"state={state}"
            )
            response = RedirectResponse(auth_url)
            response.set_cookie("mitra_oauth_state", state, httponly=True, max_age=600, samesite="lax")
            return response

        @app.get("/vault/callback")
        async def vault_callback(request: Request, code: str, state: str):
            cookie_state = request.cookies.get("mitra_oauth_state")
            if not cookie_state or cookie_state != state:
                return HTMLResponse("<h3>Error: invalid or expired state.</h3>", status_code=400)

            client_id = os.environ.get("GOOGLE_CLIENT_ID")
            client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
            web_redirect_uri = os.environ.get("GOOGLE_WEB_REDIRECT_URI")

            import httpx
            payload = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": web_redirect_uri,
                "grant_type": "authorization_code",
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post("https://oauth2.googleapis.com/token", data=payload, timeout=10.0)
            if resp.status_code != 200:
                return HTMLResponse(f"<h3>Sign-in failed</h3><pre>{resp.text}</pre>", status_code=400)

            data = resp.json()
            id_token = data.get("id_token")
            if not id_token:
                return HTMLResponse("<h3>Sign-in failed</h3><p>Google did not return an ID token.</p>", status_code=400)

            try:
                claims = token_auth.validate_bearer_token(id_token)
            except token_auth.TokenValidationError as exc:
                return HTMLResponse(f"<h3>Sign-in failed</h3><p>{exc}</p>", status_code=400)

            user_id = claims.get("email") or claims["sub"]
            response = RedirectResponse("/vault", status_code=307)
            response.set_cookie(
                "mitra_session",
                _sign(user_id),
                httponly=True,
                samesite="lax",
                secure=(request.url.scheme == "https"),
                max_age=60 * 60 * 24 * 30,
            )
            response.delete_cookie("mitra_oauth_state")
            return response

        @app.get("/vault/logout")
        async def vault_logout():
            response = RedirectResponse("/vault/login")
            response.delete_cookie("mitra_session")
            return response

        @app.get("/vault")
        async def vault_home(request: Request):
            user_id = _require_session(request)
            if not user_id:
                return RedirectResponse("/vault/login")
            keys = await get_vault_service().list_keys(user_id)
            return HTMLResponse(_vault_page(user_id, keys))

        @app.post("/vault/keys")
        async def vault_add_key(
            request: Request,
            service: str = Form(...),
            secret: str = Form(...),
            organization_url: str = Form(""),
        ):
            user_id = _require_session(request)
            if not user_id:
                return RedirectResponse("/vault/login")

            service_key = service.lower()
            if service_key not in VAULT_SERVICES:
                keys = await get_vault_service().list_keys(user_id)
                return HTMLResponse(_vault_page(user_id, keys, error=f"Unknown service: {service}"))

            metadata = {"organization_url": organization_url} if organization_url else None
            try:
                await vault_validators.validate_key(service_key, secret, metadata)
            except vault_validators.ValidationError as exc:
                keys = await get_vault_service().list_keys(user_id)
                return HTMLResponse(_vault_page(user_id, keys, error=str(exc)))

            await get_vault_service().save_key(
                user_id=user_id,
                service=service_key,
                secret=secret,
                metadata=metadata,
                last4=secret[-4:] if len(secret) >= 4 else "****",
            )
            return RedirectResponse("/vault", status_code=303)

        @app.post("/vault/keys/{service}/delete")
        async def vault_delete_key(request: Request, service: str):
            user_id = _require_session(request)
            if not user_id:
                return RedirectResponse("/vault/login")
            await get_vault_service().delete_key(user_id, service)
            return RedirectResponse("/vault", status_code=303)

        # ── Credential resolution middleware stack ──────────────────────────────────
        # Auto-collect all header → ContextVar mappings from every integration
        header_mappings = collect_headers()

        VAULT_SERVICE_SECRET_HEADERS = {
            "clockify": "x-clockify-api-key",
            "wakatime": "x-wakatime-api-key",
            "azure_devops": "x-azure-devops-pat",
        }
        VAULT_SERVICE_METADATA_HEADERS = {
            "azure_devops": {"organization_url": "x-azure-devops-org"},
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
                "authorization_servers": ["https://accounts.google.com"],
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
                claims = token_auth.validate_bearer_token(token)
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

        uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    cli()

