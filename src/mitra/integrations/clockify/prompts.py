"""Clockify prompts and resources for AI agents."""

CLOCKIFY_COMPONENT_RULES = """# Clockify Quick Reference

## Composite Tools (prefer these):
- `clockify_quick_status` — User info + running timer + today's entries in one call.
- `clockify_fill_timesheet` — WakaTime activity + Clockify status + Azure cards in one call.
- `clockify_batch_create_entries` — Create multiple entries + auto-stop timer in one call.
- `clockify_log_time_for_card` — Log time linked to an Azure DevOps card (auto-formats description).

## Atomic Tools (use only when composite tools don't fit):
- `clockify_add_time_entry` — Create a single entry (no Azure DevOps linkage).
- `clockify_update_time_entry` — Update an existing entry.
- `clockify_get_time_entries` — Fetch entries for a date range.
- `clockify_get_running_timer` — Check running timer only.
- `clockify_stop_running_timer` — Stop running timer only.
- `clockify_list_projects` — List projects (only when user asks for project mapping).
- `clockify_get_user_info` — User details (rarely needed standalone).
- `clockify_list_workspaces` — List workspaces (rarely needed).
## Strict Filling Rules:
1. **Fill Days**: ONLY fill Monday to Friday (weekdays). Skip Saturday and Sunday unless explicitly requested.
2. **Project Card Format**: Description for project work MUST format as `<short_prefix>-<card_number>: <title>` (e.g. project `gl-we-dhchat-....` -> `dhchat-card_number: title`).
3. **Break Window**: Do NOT fill work time between 1:30 PM and 3:00 PM (13:30 - 15:00) unless there is a proven work record (WakaTime activity / Google Calendar meeting) or explicitly specified in user input.
4. **User Verification**: ALWAYS ask user for verification before creating entries in Clockify.
"""


def register_prompts(mcp) -> None:
    """Register Clockify-specific prompts and resources."""

    @mcp.prompt()
    def clockify_agent_guide() -> str:
        """Component-level rules for Clockify time entry operations."""
        return CLOCKIFY_COMPONENT_RULES

    @mcp.resource("instructions://clockify-rules")
    def clockify_rules_resource() -> str:
        """Read-only Clockify component rules for AI Agents."""
        return CLOCKIFY_COMPONENT_RULES
