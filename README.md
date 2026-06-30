# Mitra MCP Server

Mitra is an all-in-one Model Context Protocol (MCP) server that integrates Clockify with local development tracking. It allows developers and AI assistants to start timers on specific files, check git diffs, and log time directly to Clockify.

## Features

- **Clockify Integration**: View workspaces, projects, active timers, and create new time entries.
- **Git Integration**: Fetch diffs, status, and history of repositories.
- **Local Timers**: Start and stop time tracking on specific files or projects, storing state locally.
- **Stdio and SSE Transport**: Run the server locally via standard I/O or host it as a remote service using Server-Sent Events (SSE).

## Installation

Clone the repository and install the package:
```bash
pip install -e .
```

## Usage

See the CLI help for options:
```bash
mitra --help
```
