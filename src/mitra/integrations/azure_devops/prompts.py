"""Azure DevOps prompts and resources for AI agents."""

AZURE_DEVOPS_COMPONENT_RULES = """# Azure DevOps Quick Reference

## Work Item Tools:
- `azure_devops_get_work_item(project, work_item_id)` — Fetch a card.
- `azure_devops_create_work_item(project, type, title, ...)` — Create a card.
- `azure_devops_update_work_item(project, work_item_id, ...)` — Update card fields.
- `azure_devops_update_work_item_state(project, work_item_id, state)` — Change card state.
- `azure_devops_search_work_items(project, ...)` — Search cards by filters.
- `azure_devops_list_work_items_by_state(project, state)` — List cards by state.

## Delivery Plans & PBI Linking Tools:
- `azure_devops_create_delivery_plan(project, name, ...)` — Create a delivery plan.
- `azure_devops_list_delivery_plans(project)` — List all delivery plans in a project.
- `azure_devops_get_delivery_plan(project, plan_id, include_timeline)` — Get plan details/timeline.
- `azure_devops_link_pbi(project, pbi_id, parent_id, start_date, target_date, ...)` — Link a PBI to a parent work item & schedule dates/iterations for Delivery Plans.

## Project Tools:
- `azure_devops_list_projects` — List org projects (only when user asks).

## Notes:
- Common states: New, Active, Resolved, Closed, Removed.
- Use `assigned_to="@me"` to find cards assigned to the current user.
"""


def register_prompts(mcp) -> None:
    """Register Azure DevOps-specific prompts and resources."""

    @mcp.prompt()
    def azure_devops_agent_guide() -> str:
        """Component-level rules for Azure DevOps work item management."""
        return AZURE_DEVOPS_COMPONENT_RULES

    @mcp.resource("instructions://azure-devops-rules")
    def azure_devops_rules_resource() -> str:
        """Read-only Azure DevOps component rules for AI Agents."""
        return AZURE_DEVOPS_COMPONENT_RULES
