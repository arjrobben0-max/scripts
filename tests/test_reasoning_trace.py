import unittest
from smartscripts.ai.reasoning_trace import build_reasoning_trace

class TestReasoningTrace(unittest.TestCase):
    def test_build_reasoning_trace_basic(self):
        input_data = {"answer": "42", "correct_answer": "43"}
        trace = build_reasoning_trace(input_data)
        self.assertIsInstance(trace, dict)
        self.assertIn("steps", trace)

if __name__ == "__main__":
    unittest.main()

