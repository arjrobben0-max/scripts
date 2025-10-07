import unittest
from smartscripts.ai.gpt_explainer import generate_explanation

class TestGPTExplainer(unittest.TestCase):
    def test_generate_explanation_basic(self):
        prompt = "Why is this answer incorrect?"
        result = generate_explanation(prompt)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

if __name__ == "__main__":
    unittest.main()


