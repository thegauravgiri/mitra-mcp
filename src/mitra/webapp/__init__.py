"""The key-vault web app: sign-in, per-service key management, and MCP connection info.

Structured as a small MVC slice on top of the same FastAPI app that serves the
MCP transport (kept on one ASGI process rather than introducing a second web
framework):
  - models:   service_config.py   (what each provider needs — the "M")
  - views:    templates/*.html    (Jinja2 — the "V")
  - controller: routes.py         (the "C" — request handling, session checks)
"""
