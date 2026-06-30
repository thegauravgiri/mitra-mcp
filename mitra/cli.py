import click
import uvicorn
from fastapi import FastAPI
from mitra.server import mcp
from mitra.config import load_config, save_config

@click.group()
def cli():
    """Mitra CLI: Manage the Mitra MCP Server and settings."""
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
        click.echo(f"Starting Mitra MCP server in SSE mode on http://{host}:{port} ...", err=True)
        app = FastAPI(title="Mitra Remote MCP Server")
        app.mount("/", mcp.streamable_http_app())
        uvicorn.run(app, host=host, port=port)

@cli.group()
def config():
    """Manage configuration settings (API keys, workspace IDs, etc.)."""
    pass

@config.command("show")
def config_show():
    """Show the current configuration parameters."""
    conf = load_config()
    if not conf:
        click.echo("No configuration found. Use 'mitra config set' to create one.")
        return
    for k, v in conf.items():
        if k == "CLOCKIFY_API_KEY" and v:
            masked_key = v[:4] + "*" * (len(v) - 8) + v[-4:] if len(v) > 8 else "********"
            click.echo(f"{k}: {masked_key}")
        else:
            click.echo(f"{k}: {v}")

@config.command("set")
@click.option("--api-key", help="Your Clockify API Key.")
@click.option("--workspace", help="Default workspace ID for tracking.")
@click.option("--project", help="Default project ID for tracking.")
def config_set(api_key, workspace, project):
    """Set one or more configuration parameters."""
    if not api_key and not workspace and not project:
        click.echo("Please provide at least one parameter to set (e.g., --api-key, --workspace, --project).")
        return
        
    conf = load_config()
    if api_key:
        conf["CLOCKIFY_API_KEY"] = api_key
    if workspace:
        conf["CLOCKIFY_WORKSPACE_ID"] = workspace
    if project:
        conf["CLOCKIFY_PROJECT_ID"] = project
        
    save_config(conf)
    click.echo("Configuration updated successfully.")

if __name__ == "__main__":
    cli()
