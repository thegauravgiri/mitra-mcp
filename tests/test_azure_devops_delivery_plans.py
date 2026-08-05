import unittest
from unittest.mock import AsyncMock, patch
from mitra.integrations.azure_devops.client import AzureDevOpsClient


class TestAzureDevOpsDeliveryPlans(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = AzureDevOpsClient(pat="dummy-pat", organization_url="https://dev.azure.com/dummy-org")

    @patch.object(AzureDevOpsClient, "_request", new_callable=AsyncMock)
    async def test_list_delivery_plans(self, mock_request):
        mock_request.return_value = {
            "value": [
                {
                    "id": "plan-1",
                    "name": "Q3 Delivery Plan",
                    "description": "Roadmap for Q3",
                    "type": "deliveryTimelineView",
                }
            ]
        }

        plans = await self.client.list_delivery_plans("test-project")
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["id"], "plan-1")
        self.assertEqual(plans[0]["name"], "Q3 Delivery Plan")
        mock_request.assert_called_once_with(
            "GET",
            "https://dev.azure.com/dummy-org/test-project/_apis/work/plans",
            params={"api-version": "7.0-preview.1"}
        )

    @patch.object(AzureDevOpsClient, "_request", new_callable=AsyncMock)
    async def test_get_delivery_plan_with_timeline(self, mock_request):
        mock_request.side_effect = [
            {"id": "plan-1", "name": "Q3 Delivery Plan", "properties": {}},
            {"teams": [], "workItems": [{"id": 101}]}
        ]

        plan = await self.client.get_delivery_plan("test-project", "plan-1", include_timeline=True)
        self.assertEqual(plan["id"], "plan-1")
        self.assertIn("timeline", plan)
        self.assertEqual(plan["timeline"]["workItems"][0]["id"], 101)

    @patch.object(AzureDevOpsClient, "_request", new_callable=AsyncMock)
    async def test_create_delivery_plan(self, mock_request):
        mock_request.return_value = {
            "id": "plan-new",
            "name": "Release 2.0 Plan",
            "type": "deliveryTimelineView",
        }

        result = await self.client.create_delivery_plan(
            project="test-project",
            name="Release 2.0 Plan",
            description="Delivery plan for v2.0 release",
        )
        self.assertEqual(result["id"], "plan-new")
        self.assertEqual(result["name"], "Release 2.0 Plan")
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args.kwargs
        self.assertEqual(call_kwargs["json_data"]["name"], "Release 2.0 Plan")

    @patch.object(AzureDevOpsClient, "_request", new_callable=AsyncMock)
    async def test_link_pbi(self, mock_request):
        mock_request.return_value = {
            "id": 200,
            "fields": {
                "System.Title": "PBI 200",
                "System.IterationPath": "test-project\\Sprint 5",
                "Microsoft.VSTS.Scheduling.StartDate": "2026-08-01",
                "Microsoft.VSTS.Scheduling.TargetDate": "2026-08-15",
            }
        }

        result = await self.client.link_pbi(
            project="test-project",
            pbi_id=200,
            parent_id=100,
            iteration_path="test-project\\Sprint 5",
            start_date="2026-08-01",
            target_date="2026-08-15",
        )
        self.assertEqual(result["id"], 200)
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args.args[0], "PATCH")
        ops = call_args.kwargs["json_data"]
        # Verify relation operation included
        rel_op = [op for op in ops if op.get("path") == "/relations/-"]
        self.assertEqual(len(rel_op), 1)
        self.assertIn("100", rel_op[0]["value"]["url"])

    async def test_link_pbi_no_arguments_raises(self):
        with self.assertRaises(ValueError):
            await self.client.link_pbi(project="test-project", pbi_id=200)


if __name__ == "__main__":
    unittest.main()
