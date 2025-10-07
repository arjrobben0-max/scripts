import unittest
from smartscripts.ai.bias_detector import detect_bias

class TestBiasDetector(unittest.TestCase):
    def test_detect_bias_empty(self):
        data = []
        result = detect_bias(data)
        self.assertFalse(result)  # Expect no bias detected in empty data

    def test_detect_bias_sample(self):
        data = [{"grader": "A", "score": 5}, {"grader": "B", "score": 1}]
        result = detect_bias(data)
        self.assertIsInstance(result, bool)

if __name__ == "__main__":
    unittest.main()

