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
        from mitra.core.registry import collect_headers

        click.echo(f"Starting Mitra MCP server in SSE mode on http://{host}:{port} ...", err=True)

        @contextlib.asynccontextmanager
        async def lifespan(app: FastAPI):
            async with mcp.session_manager.run():
                yield

        app = FastAPI(title="Mitra Remote MCP Server", lifespan=lifespan)

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
