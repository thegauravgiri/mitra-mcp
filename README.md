# Mitra MCP Server

Mitra is a Model Context Protocol (MCP) server that integrates Clockify with WakaTime coding tracking. It allows developers and local AI assistants to fetch active projects, check file-level coding durations via WakaTime, and log time entries directly to Clockify.

## Features

- **Clockify Integration**: View workspaces, projects, running timers, and log new time entries.
- **WakaTime Integration**: Fetch active projects and detailed file-level coding durations for today.
- **Stdio and SSE Transport**: Run the server locally via standard I/O or host it as a remote service using Server-Sent Events (SSE).


## Installation

Clone the repository and install the package:
```bash
pip install -e .
```

## Setup

Configure your Clockify and WakaTime credentials interactively:
```bash
mitra setup
```
This command will prompt you for your Clockify API Key and WakaTime API Key, validate both, and help you select your default Clockify workspace and project.


## Usage

Start the Mitra MCP Server in local `stdio` mode:
```bash
mitra start --transport stdio
```

Or run in SSE mode for remote clients:
```bash
mitra start --transport sse --host 127.0.0.1 --port 8000
```

For more CLI options:
```bash
mitra --help
```


