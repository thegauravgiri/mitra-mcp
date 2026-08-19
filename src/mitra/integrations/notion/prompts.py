"""Notion prompts and resources for AI agents.

The Notion Dashboard skill is authored and maintained outside this repository and
fetched over HTTP on first use, then cached for the lifetime of the process.
"""

import logging

import httpx

logger = logging.getLogger("mitra.integrations.notion.prompts")

NOTION_SKILL_URL = (
    "https://gist.githubusercontent.com/thegauravgiri/"
    "a25f9a0429e09c4a713eef9298507976/raw/"
    "5a479a3f895bc9ae71ce6e5fc5f44a5b94bb89c7/MyNotionDashboardSkill.md"
)

NOTION_SKILL_UNAVAILABLE = """# Notion Dashboard Skill (unavailable)

The Notion Dashboard skill could not be fetched from its source URL.
Do not guess database IDs or property names — tell the user the skill is
unavailable and ask them to retry once connectivity is restored.
"""

_cache: str | None = None


async def fetch_notion_skill() -> str:
    """Fetch the Notion Dashboard skill markdown, caching it after the first success.

    Returns:
        The skill markdown, or a placeholder notice if the fetch fails.
    """
    global _cache
    if _cache is not None:
        return _cache

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(NOTION_SKILL_URL)
            response.raise_for_status()
    except Exception:
        logger.exception(f"Failed to fetch Notion skill from {NOTION_SKILL_URL}")
        return NOTION_SKILL_UNAVAILABLE

    _cache = response.text
    return _cache


def register_prompts(mcp) -> None:
    """Register Notion-specific prompts and resources."""

    @mcp.prompt()
    async def notion_dashboard_skill() -> str:
        """How to add, edit, update, and remove information in the Notion Dashboard and its linked databases (Todo, Tasks, Codepad, Project Planner). Read this before any Notion operation."""
        return await fetch_notion_skill()

    @mcp.resource("skills://notion-dashboard-skill")
    async def notion_dashboard_skill_resource() -> str:
        """Read-only Notion Dashboard information-architecture skill for AI Agents."""
        return await fetch_notion_skill()
