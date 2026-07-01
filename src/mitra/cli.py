import click
import uvicorn
from fastapi import FastAPI
import asyncio
from mitra.server import mcp
from mitra.config import load_config, save_config
from mitra.clockify import ClockifyClient

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
            from mitra.config import (
                request_api_key,
                request_workspace_id,
                request_project_id,
                request_wakatime_api_key,
            )
            
            # Extract headers (FastAPI headers are case-insensitive)
            api_key = request.headers.get("x-clockify-api-key")
            workspace_id = request.headers.get("x-clockify-workspace-id")
            project_id = request.headers.get("x-clockify-project-id")
            wakatime_key = request.headers.get("x-wakatime-api-key")
            
            # Set context tokens
            token_api = request_api_key.set(api_key) if api_key else None
            token_ws = request_workspace_id.set(workspace_id) if workspace_id else None
            token_proj = request_project_id.set(project_id) if project_id else None
            token_waka = request_wakatime_api_key.set(wakatime_key) if wakatime_key else None
            
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
        if k in ("CLOCKIFY_API_KEY", "WAKATIME_API_KEY") and v:
            masked_key = v[:4] + "*" * (len(v) - 8) + v[-4:] if len(v) > 8 else "********"
            click.echo(f"{k}: {masked_key}")
        else:
            click.echo(f"{k}: {v}")

@config.command("set")
@click.option("--api-key", help="Your Clockify API Key.")
@click.option("--wakatime-key", help="Your WakaTime API Key.")
@click.option("--workspace", help="Default workspace ID for tracking.")
@click.option("--project", help="Default project ID for tracking.")
def config_set(api_key, wakatime_key, workspace, project):
    """Set one or more configuration parameters."""
    if not api_key and not wakatime_key and not workspace and not project:
        click.echo("Please provide at least one parameter to set (e.g., --api-key, --wakatime-key, --workspace, --project).")
        return
        
    conf = load_config()
    if api_key:
        conf["CLOCKIFY_API_KEY"] = api_key
    if wakatime_key:
        conf["WAKATIME_API_KEY"] = wakatime_key
    if workspace:
        conf["CLOCKIFY_WORKSPACE_ID"] = workspace
    if project:
        conf["CLOCKIFY_PROJECT_ID"] = project
        
    save_config(conf)
    click.echo("Configuration updated successfully.")


@cli.command("setup")
def setup():
    """Interactive setup to configure Clockify credentials."""
    click.echo("=== Mitra Clockify Setup ===")
    
    # 1. API Key
    api_key = click.prompt("Enter your Clockify API Key", hide_input=True)
    if not api_key:
        click.echo("API key cannot be empty.")
        return
        
    client = ClockifyClient(api_key)
    
    # 2. Validate API Key by fetching user info
    try:
        click.echo("Validating API Key...")
        user_info = asyncio.run(client.get_current_user())
        click.echo(f"Success! Authenticated as: {user_info.get('name')} ({user_info.get('email')})")
    except Exception as e:
        click.echo(f"Warning: Failed to authenticate with Clockify API key: {e}")
        if not click.confirm("Do you want to use this API key anyway?", default=True):
            return
        
    # 3. Workspaces
    workspace_id = None
    workspaces = []
    try:
        click.echo("Fetching workspaces...")
        workspaces = asyncio.run(client.get_workspaces())
    except Exception as e:
        click.echo(f"Warning: Could not fetch workspaces: {e}")
        
    if workspaces:
        if len(workspaces) == 1:
            workspace = workspaces[0]
            workspace_id = workspace["id"]
            click.echo(f"Default Workspace: {workspace['name']} (automatically set)")
        else:
            click.echo("\nAvailable Workspaces:")
            for idx, ws in enumerate(workspaces, start=1):
                click.echo(f"  {idx}. {ws['name']} (ID: {ws['id']})")
            
            choice = click.prompt(
                "Select a workspace (enter number)",
                type=click.IntRange(1, len(workspaces))
            )
            workspace = workspaces[choice - 1]
            workspace_id = workspace["id"]
            click.echo(f"Workspace set to: {workspace['name']}")
    else:
        workspace_id = click.prompt("Enter default Clockify Workspace ID (optional)", default="")
        if not workspace_id:
            workspace_id = None
        
    # 4. Projects (Optional)
    project_id = None
    projects = []
    if workspace_id:
        try:
            click.echo("\nFetching projects...")
            projects = asyncio.run(client.get_projects(workspace_id))
        except Exception as e:
            click.echo(f"Warning: Could not fetch projects: {e}")
            
        if projects:
            click.echo("Available Projects:")
            click.echo("  0. Skip / No default project")
            for idx, proj in enumerate(projects, start=1):
                click.echo(f"  {idx}. {proj['name']} (ID: {proj['id']})")
                
            choice = click.prompt(
                "Select a default project (enter number or 0 to skip)",
                type=click.IntRange(0, len(projects)),
                default=0
            )
            if choice > 0:
                project = projects[choice - 1]
                project_id = project["id"]
                click.echo(f"Default project set to: {project['name']}")
            else:
                click.echo("No default project set.")
        else:
            click.echo("No projects found in this workspace. Skipping default project selection.")

        
    # 5. WakaTime Setup
    click.echo("\n=== WakaTime Setup ===")
    from mitra.wakatime import get_wakatime_api_key
    waka_key = get_wakatime_api_key()
    
    prompt_waka = True
    if waka_key:
        masked_waka = waka_key[:4] + "*" * (len(waka_key) - 8) + waka_key[-4:] if len(waka_key) > 8 else "********"
        click.echo(f"Found existing WakaTime API Key: {masked_waka}")
        if not click.confirm("Do you want to overwrite / configure a new WakaTime API Key?", default=False):
            prompt_waka = False
            
    waka_api_key = waka_key
    if prompt_waka:
        waka_api_key = click.prompt("Enter your WakaTime API Key", hide_input=True)
        if waka_api_key:
            from mitra.wakatime import WakaTimeClient
            try:
                click.echo("Validating WakaTime API Key...")
                client_waka = WakaTimeClient(waka_api_key)
                asyncio.run(client_waka.get_today_projects())
                click.echo("Success! WakaTime API Key is valid.")
            except Exception as e:
                click.echo(f"Warning: Failed to validate WakaTime API key: {e}")
                if not click.confirm("Do you want to use this API key anyway?", default=True):
                    return
        else:
            click.echo("WakaTime API key cannot be empty.")
            return

    # 6. Save Configuration
    conf = load_config()
    conf["CLOCKIFY_API_KEY"] = api_key
    conf["CLOCKIFY_WORKSPACE_ID"] = workspace_id
    if project_id:
        conf["CLOCKIFY_PROJECT_ID"] = project_id
    else:
        conf.pop("CLOCKIFY_PROJECT_ID", None)
        
    if waka_api_key:
        conf["WAKATIME_API_KEY"] = waka_api_key
        
    save_config(conf)
    click.echo("\nConfiguration updated and saved successfully.")

if __name__ == "__main__":
    cli()


