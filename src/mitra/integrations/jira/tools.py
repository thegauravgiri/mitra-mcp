"""Jira MCP tool registrations."""

from typing import Optional, List, Dict, Any

from mitra.integrations.jira.client import JiraClient
from mitra.integrations.jira.context import get_jira_email, get_jira_api_token, get_jira_url


def _resolve_jira_config(
    email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
) -> tuple:
    """Resolve Jira email, API token, and site URL from parameters or environment variables."""
    resolved_email = email or get_jira_email()
    resolved_token = api_token or get_jira_api_token()
    resolved_url = site_url or get_jira_url()
    if not resolved_email:
        raise ValueError(
            "Jira account email not found. Please provide the 'email' parameter, "
            "set it via client headers, or set the JIRA_EMAIL environment variable."
        )
    if not resolved_token:
        raise ValueError(
            "Jira API token not found. Please provide the 'api_token' parameter, "
            "set it via client headers, or set the JIRA_API_TOKEN environment variable."
        )
    if not resolved_url:
        raise ValueError(
            "Jira site URL not found. Please provide the 'site_url' parameter, "
            "set it via client headers, or set the JIRA_URL environment variable."
        )
    return resolved_email, resolved_token, resolved_url


def register_tools(mcp) -> None:
    """Register all Jira tools with the MCP server."""

    # --- Project Tools ---

    @mcp.tool()
    async def jira_list_projects(
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists all Jira projects visible to the authenticated user."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        return await client.list_projects()

    @mcp.tool()
    async def jira_get_project(
        project_key: str,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetches a single Jira project's details by key or ID."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        return await client.get_project(project_key)

    @mcp.tool()
    async def jira_list_issue_types(
        project_key: str,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists issue types (Task, Bug, Story, Epic, Sub-task, etc.) available in a project."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        return await client.list_issue_types(project_key)

    # --- Issue CRUD Tools ---

    @mcp.tool()
    async def jira_get_issue(
        issue_key: str,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetches a single Jira issue by its key (e.g. 'PROJ-123').
        Returns a clean summary with key, summary, type, status, priority, assignee, and URL.
        """
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        raw = await client.get_issue(issue_key)
        return JiraClient.format_issue_summary(raw)

    @mcp.tool()
    async def jira_create_issue(
        project_key: str, issue_type: str, summary: str,
        description: Optional[str] = None, assignee_email: Optional[str] = None,
        priority: Optional[str] = None, labels: Optional[List[str]] = None,
        parent_key: Optional[str] = None, components: Optional[List[str]] = None,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new Jira issue in a project.
        issue_type can be 'Task', 'Bug', 'Story', 'Epic', 'Sub-task', etc. (see jira_list_issue_types).
        assignee_email is resolved to a Jira accountId automatically.
        parent_key links this issue under an Epic or, for Sub-task types, under a parent issue.
        """
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        account_id = await client.find_account_id(assignee_email) if assignee_email else None
        raw = await client.create_issue(
            project_key=project_key, issue_type=issue_type, summary=summary,
            description=description, assignee_account_id=account_id, priority=priority,
            labels=labels, parent_key=parent_key, components=components,
        )
        created = await client.get_issue(raw["key"])
        return JiraClient.format_issue_summary(created)

    @mcp.tool()
    async def jira_update_issue(
        issue_key: str,
        summary: Optional[str] = None, description: Optional[str] = None,
        assignee_email: Optional[str] = None, priority: Optional[str] = None,
        labels: Optional[List[str]] = None, components: Optional[List[str]] = None,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Updates an existing Jira issue's fields. Only the provided fields will be updated.
        assignee_email is resolved to a Jira accountId automatically.
        """
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        account_id = await client.find_account_id(assignee_email) if assignee_email else None
        await client.update_issue(
            issue_key=issue_key, summary=summary, description=description,
            assignee_account_id=account_id, priority=priority, labels=labels, components=components,
        )
        updated = await client.get_issue(issue_key)
        return JiraClient.format_issue_summary(updated)

    @mcp.tool()
    async def jira_delete_issue(
        issue_key: str, delete_subtasks: bool = True,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """Permanently deletes a Jira issue. This cannot be undone."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        await client.delete_issue(issue_key, delete_subtasks=delete_subtasks)
        return {"status": "deleted", "issue_key": issue_key}

    @mcp.tool()
    async def jira_assign_issue(
        issue_key: str, assignee_email: Optional[str] = None,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Assigns a Jira issue to a user by email. Pass assignee_email=None to unassign the issue.
        """
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        account_id = await client.find_account_id(assignee_email) if assignee_email else None
        if assignee_email and not account_id:
            raise ValueError(f"No Jira user found matching '{assignee_email}'.")
        await client.assign_issue(issue_key, account_id)
        return {"status": "assigned" if account_id else "unassigned", "issue_key": issue_key}

    @mcp.tool()
    async def jira_search_issues(
        jql: str, max_results: int = 50, fields: Optional[List[str]] = None,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches Jira issues using JQL (Jira Query Language).
        Examples: "project = PROJ AND status = 'In Progress'", "assignee = currentUser() ORDER BY updated DESC".
        Returns up to 'max_results' results (default 50).
        """
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        result = await client.search_issues(jql=jql, max_results=max_results, fields=fields)
        issues = result.get("issues", []) if isinstance(result, dict) else []
        return [JiraClient.format_issue_summary(i) for i in issues]

    @mcp.tool()
    async def jira_list_issues_by_status(
        project_key: str, status: str, issue_type: Optional[str] = None, max_results: int = 50,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lists Jira issues filtered by status in a project.
        Common statuses: 'To Do', 'In Progress', 'Done' (actual names depend on the project's workflow).
        Optionally filter by issue_type (e.g. 'Bug', 'Task').
        """
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        conditions = [f"project = \"{project_key}\"", f"status = \"{status}\""]
        if issue_type:
            conditions.append(f"issuetype = \"{issue_type}\"")
        jql = f"{' AND '.join(conditions)} ORDER BY updated DESC"
        result = await client.search_issues(jql=jql, max_results=max_results)
        issues = result.get("issues", []) if isinstance(result, dict) else []
        return [JiraClient.format_issue_summary(i) for i in issues]

    # --- Transition (Status) Tools ---

    @mcp.tool()
    async def jira_list_transitions(
        issue_key: str,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists the workflow transitions currently available for a Jira issue."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        transitions = await client.list_transitions(issue_key)
        return [
            {"id": t.get("id"), "name": t.get("name"), "to_status": (t.get("to") or {}).get("name")}
            for t in transitions
        ]

    @mcp.tool()
    async def jira_transition_issue(
        issue_key: str, transition: str, comment: Optional[str] = None,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Moves a Jira issue through its workflow (e.g. change status to 'In Progress' or 'Done').
        `transition` can be a transition name (case-insensitive) or ID — see jira_list_transitions.
        Optionally attach a comment while transitioning.
        """
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        await client.transition_issue(issue_key, transition, comment=comment)
        updated = await client.get_issue(issue_key)
        return JiraClient.format_issue_summary(updated)

    # --- Comment CRUD Tools ---

    @mcp.tool()
    async def jira_list_comments(
        issue_key: str,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists all comments on a Jira issue."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        comments = await client.list_comments(issue_key)
        return [JiraClient.format_comment_summary(c) for c in comments]

    @mcp.tool()
    async def jira_add_comment(
        issue_key: str, body: str,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Adds a comment to a Jira issue."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        raw = await client.add_comment(issue_key, body)
        return JiraClient.format_comment_summary(raw)

    @mcp.tool()
    async def jira_update_comment(
        issue_key: str, comment_id: str, body: str,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Updates an existing comment on a Jira issue."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        raw = await client.update_comment(issue_key, comment_id, body)
        return JiraClient.format_comment_summary(raw)

    @mcp.tool()
    async def jira_delete_comment(
        issue_key: str, comment_id: str,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """Deletes a comment from a Jira issue."""
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        await client.delete_comment(issue_key, comment_id)
        return {"status": "deleted", "issue_key": issue_key, "comment_id": comment_id}

    # --- Issue Link Tools ---

    @mcp.tool()
    async def jira_link_issues(
        inward_key: str, outward_key: str, link_type: str = "Relates", comment: Optional[str] = None,
        email: Optional[str] = None, api_token: Optional[str] = None, site_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Creates a link between two Jira issues.
        link_type examples: 'Relates', 'Blocks', 'Duplicate', 'Cloners' (depends on Jira instance configuration).
        For directional types like 'Blocks', inward_key is the issue that is blocked by outward_key.
        """
        resolved_email, resolved_token, resolved_url = _resolve_jira_config(email, api_token, site_url)
        client = JiraClient(resolved_email, resolved_token, resolved_url)
        await client.link_issues(inward_key, outward_key, link_type=link_type, comment=comment)
        return {"status": "linked", "inward_key": inward_key, "outward_key": outward_key, "link_type": link_type}
