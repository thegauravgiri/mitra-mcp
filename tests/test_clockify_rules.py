import unittest
from mitra.integrations.azure_devops.client import AzureDevOpsClient


class TestClockifyRules(unittest.TestCase):

    def test_generate_project_slug(self):
        # gl-we-dhchat-.... -> dhchat
        self.assertEqual(
            AzureDevOpsClient.generate_project_slug("gl-we-dhchat-backend"),
            "dhchat"
        )
        self.assertEqual(
            AzureDevOpsClient.generate_project_slug("gl-we-dhchat"),
            "dhchat"
        )
        self.assertEqual(
            AzureDevOpsClient.generate_project_slug("Customer Portal"),
            "customer"
        )

    def test_format_clockify_description(self):
        slug = AzureDevOpsClient.generate_project_slug("gl-we-dhchat-mobile")
        desc = AzureDevOpsClient.format_clockify_description(slug, 42, "Fix login issue")
        self.assertEqual(desc, "dhchat-42: Fix login issue")


if __name__ == "__main__":
    unittest.main()
