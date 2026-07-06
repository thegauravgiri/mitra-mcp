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
        from fastapi import Request
        click.echo(f"Starting Mitra MCP server in SSE mode on http://{host}:{port} ...", err=True)
        
        @contextlib.asynccontextmanager
        async def lifespan(app: FastAPI):
            async with mcp.session_manager.run():
                yield
                
        app = FastAPI(title="Mitra Remote MCP Server", lifespan=lifespan)
        
        @app.middleware("http")
        async def extract_headers_middleware(request: Request, call_next):
            from mitra.context import (
                request_api_key,
                request_workspace_id,
                request_project_id,
                request_wakatime_api_key,
                request_azure_devops_pat,
                request_azure_devops_org,
            )
            
            # Extract headers (FastAPI headers are case-insensitive)
            api_key = request.headers.get("x-clockify-api-key")
            workspace_id = request.headers.get("x-clockify-workspace-id")
            project_id = request.headers.get("x-clockify-project-id")
            wakatime_key = request.headers.get("x-wakatime-api-key")
            azure_pat = request.headers.get("x-azure-devops-pat")
            azure_org = request.headers.get("x-azure-devops-org")
            
            # Set context tokens
            token_api = request_api_key.set(api_key) if api_key else None
            token_ws = request_workspace_id.set(workspace_id) if workspace_id else None
            token_proj = request_project_id.set(project_id) if project_id else None
            token_waka = request_wakatime_api_key.set(wakatime_key) if wakatime_key else None
            token_azure_pat = request_azure_devops_pat.set(azure_pat) if azure_pat else None
            token_azure_org = request_azure_devops_org.set(azure_org) if azure_org else None
            
            try:
                response = await call_next(request)
                return response
            finally:
                if token_api:
                    request_api_key.reset(token_api)
                if token_ws:
                    request_workspace_id.reset(token_ws)
                if token_proj:
                    request_project_id.reset(token_proj)
                if token_waka:
                    request_wakatime_api_key.reset(token_waka)
                if token_azure_pat:
                    request_azure_devops_pat.reset(token_azure_pat)
                if token_azure_org:
                    request_azure_devops_org.reset(token_azure_org)

        app.mount("/", mcp.streamable_http_app())
        uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    cli()
