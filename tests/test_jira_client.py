import unittest
from unittest.mock import AsyncMock, patch
from mitra.integrations.jira.client import JiraClient


class TestJiraClient(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = JiraClient(
            email="dummy@example.com", api_token="dummy-token", site_url="https://dummy.atlassian.net"
        )

    def test_text_to_adf(self):
        adf = JiraClient.text_to_adf("hello world")
        self.assertEqual(adf["type"], "doc")
        self.assertEqual(adf["content"][0]["content"][0]["text"], "hello world")

    def test_text_to_adf_passthrough_dict(self):
        raw = {"type": "doc", "version": 1, "content": []}
        self.assertIs(JiraClient.text_to_adf(raw), raw)

    def test_adf_to_text(self):
        adf = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]}
            ],
        }
        self.assertEqual(JiraClient.adf_to_text(adf), "hello world")

    def test_adf_to_text_none(self):
        self.assertIsNone(JiraClient.adf_to_text(None))

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_list_projects(self, mock_request):
        mock_request.return_value = {"values": [{"key": "PROJ", "name": "Project"}]}
        projects = await self.client.list_projects()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["key"], "PROJ")
        mock_request.assert_called_once_with(
            "GET", "https://dummy.atlassian.net/rest/api/3/project/search", params={"maxResults": 100}
        )

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_get_issue(self, mock_request):
        mock_request.return_value = {"key": "PROJ-1", "id": "1", "fields": {"summary": "Test"}}
        issue = await self.client.get_issue("PROJ-1")
        self.assertEqual(issue["key"], "PROJ-1")
        mock_request.assert_called_once_with(
            "GET", "https://dummy.atlassian.net/rest/api/3/issue/PROJ-1", params={}
        )

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_create_issue(self, mock_request):
        mock_request.return_value = {"key": "PROJ-2", "id": "2"}
        result = await self.client.create_issue(
            project_key="PROJ", issue_type="Task", summary="New task", description="A description",
            priority="High", labels=["backend"],
        )
        self.assertEqual(result["key"], "PROJ-2")
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args.kwargs
        fields = call_kwargs["json_data"]["fields"]
        self.assertEqual(fields["project"], {"key": "PROJ"})
        self.assertEqual(fields["issuetype"], {"name": "Task"})
        self.assertEqual(fields["summary"], "New task")
        self.assertEqual(fields["priority"], {"name": "High"})
        self.assertEqual(fields["labels"], ["backend"])
        self.assertEqual(fields["description"]["type"], "doc")

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_update_issue(self, mock_request):
        mock_request.return_value = None
        await self.client.update_issue("PROJ-1", summary="Updated title")
        mock_request.assert_called_once_with(
            "PUT",
            "https://dummy.atlassian.net/rest/api/3/issue/PROJ-1",
            json_data={"fields": {"summary": "Updated title"}},
        )

    async def test_update_issue_no_fields_raises(self):
        with self.assertRaises(ValueError):
            await self.client.update_issue("PROJ-1")

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_delete_issue(self, mock_request):
        mock_request.return_value = None
        await self.client.delete_issue("PROJ-1")
        mock_request.assert_called_once_with(
            "DELETE",
            "https://dummy.atlassian.net/rest/api/3/issue/PROJ-1",
            params={"deleteSubtasks": "true"},
        )

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_search_issues(self, mock_request):
        mock_request.return_value = {"issues": [{"key": "PROJ-1", "fields": {}}], "nextPageToken": None}
        result = await self.client.search_issues("project = PROJ")
        self.assertEqual(len(result["issues"]), 1)
        call_kwargs = mock_request.call_args.kwargs
        self.assertEqual(call_kwargs["json_data"]["jql"], "project = PROJ")

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_transition_issue_by_name(self, mock_request):
        mock_request.side_effect = [
            {"transitions": [{"id": "31", "name": "Done"}, {"id": "21", "name": "In Progress"}]},
            None,
        ]
        await self.client.transition_issue("PROJ-1", "done")
        second_call = mock_request.call_args_list[1]
        self.assertEqual(second_call.args[0], "POST")
        self.assertEqual(second_call.kwargs["json_data"]["transition"], {"id": "31"})

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_transition_issue_unknown_raises(self, mock_request):
        mock_request.return_value = {"transitions": [{"id": "31", "name": "Done"}]}
        with self.assertRaises(ValueError):
            await self.client.transition_issue("PROJ-1", "Nonexistent")

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_add_comment(self, mock_request):
        mock_request.return_value = {"id": "100", "body": {}, "author": {"displayName": "Test User"}}
        result = await self.client.add_comment("PROJ-1", "A comment")
        self.assertEqual(result["id"], "100")
        call_kwargs = mock_request.call_args.kwargs
        self.assertEqual(call_kwargs["json_data"]["body"]["type"], "doc")

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_link_issues(self, mock_request):
        mock_request.return_value = None
        await self.client.link_issues("PROJ-1", "PROJ-2", link_type="Blocks")
        call_kwargs = mock_request.call_args.kwargs
        self.assertEqual(call_kwargs["json_data"]["type"], {"name": "Blocks"})
        self.assertEqual(call_kwargs["json_data"]["inwardIssue"], {"key": "PROJ-1"})
        self.assertEqual(call_kwargs["json_data"]["outwardIssue"], {"key": "PROJ-2"})

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_find_account_id(self, mock_request):
        mock_request.return_value = [{"accountId": "abc123"}]
        account_id = await self.client.find_account_id("someone@example.com")
        self.assertEqual(account_id, "abc123")

    @patch.object(JiraClient, "_request", new_callable=AsyncMock)
    async def test_find_account_id_no_match(self, mock_request):
        mock_request.return_value = []
        account_id = await self.client.find_account_id("nobody@example.com")
        self.assertIsNone(account_id)

    def test_format_issue_summary(self):
        raw = {
            "key": "PROJ-1",
            "id": "1",
            "self": "https://dummy.atlassian.net/rest/api/3/issue/1",
            "fields": {
                "summary": "Test issue",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "issuetype": {"name": "Bug"},
                "assignee": {"displayName": "Jane Doe", "accountId": "acc-1"},
                "project": {"key": "PROJ"},
            },
        }
        summary = JiraClient.format_issue_summary(raw)
        self.assertEqual(summary["key"], "PROJ-1")
        self.assertEqual(summary["status"], "In Progress")
        self.assertEqual(summary["assignee"], "Jane Doe")
        self.assertEqual(summary["assignee_account_id"], "acc-1")
        self.assertEqual(summary["url"], "https://dummy.atlassian.net/browse/PROJ-1")


if __name__ == "__main__":
    unittest.main()
