"""Jira prompts and resources for AI agents."""

JIRA_COMPONENT_RULES = """# Jira Quick Reference

## Issue Tools:
- `jira_get_issue(issue_key)` — Fetch an issue.
- `jira_create_issue(project_key, issue_type, summary, ...)` — Create an issue.
- `jira_update_issue(issue_key, ...)` — Update issue fields.
- `jira_delete_issue(issue_key)` — Permanently delete an issue.
- `jira_assign_issue(issue_key, assignee_email)` — Assign or unassign (pass no email) an issue.
- `jira_search_issues(jql, ...)` — Search issues using JQL.
- `jira_list_issues_by_status(project_key, status, ...)` — List issues by status.

## Status / Workflow Tools:
- `jira_list_transitions(issue_key)` — List available status transitions for an issue.
- `jira_transition_issue(issue_key, transition, comment)` — Move an issue to a new status.

## Comment Tools:
- `jira_list_comments(issue_key)` — List comments on an issue.
- `jira_add_comment(issue_key, body)` — Add a comment.
- `jira_update_comment(issue_key, comment_id, body)` — Update a comment.
- `jira_delete_comment(issue_key, comment_id)` — Delete a comment.

## Linking Tools:
- `jira_link_issues(inward_key, outward_key, link_type)` — Link two issues (e.g. 'Blocks', 'Relates').

## Project Tools:
- `jira_list_projects()` — List visible projects (only when user asks).
- `jira_get_project(project_key)` — Get project details.
- `jira_list_issue_types(project_key)` — List issue types available in a project (Task, Bug, Story, Epic, Sub-task, ...).

## Notes:
- Status names are workflow-specific — check `jira_list_transitions` before transitioning rather than guessing.
- Assignees are looked up by email and resolved to Jira accountIds automatically.
- JQL examples: "project = PROJ AND status = 'In Progress'", "assignee = currentUser() ORDER BY updated DESC".
"""


def register_prompts(mcp) -> None:
    """Register Jira-specific prompts and resources."""

    @mcp.prompt()
    def jira_agent_guide() -> str:
        """Component-level rules for Jira issue management."""
        return JIRA_COMPONENT_RULES

    @mcp.resource("instructions://jira-rules")
    def jira_rules_resource() -> str:
        """Read-only Jira component rules for AI Agents."""
        return JIRA_COMPONENT_RULES
