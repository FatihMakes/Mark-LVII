"""
tests/test_h3_3_browser.py — Tests for Autonomous Browser Agent
"""
import unittest
from core.browser_agent import BrowserAgent, get_browser_agent
from actions.browser_control import browser_control


class TestBrowserAgent(unittest.TestCase):

    def setUp(self):
        self.agent = BrowserAgent(headless=True)

    def test_goal_understanding_arxiv(self):
        res = self.agent._understand_goal("Find AI papers on arxiv")
        self.assertEqual(res["type"], "search")
        self.assertIn("arxiv.org", res["start_url"])

    def test_goal_understanding_direct_url(self):
        res = self.agent._understand_goal("Check status on https://example.org/status")
        self.assertEqual(res["type"], "direct_url")
        self.assertEqual(res["start_url"], "https://example.org/status")

    def test_plan_formulation(self):
        understanding = {"type": "search", "query": "python", "start_url": "https://duckduckgo.com"}
        plan = self.agent._create_execution_plan(understanding)
        self.assertTrue(len(plan) > 0)
        actions = [p["action"] for p in plan]
        self.assertIn("scroll_down", actions)

    def test_browser_control_action_agent(self):
        res = browser_control({"action": "agent"})
        self.assertIn("Please specify a browsing goal", res)


if __name__ == "__main__":
    unittest.main()
