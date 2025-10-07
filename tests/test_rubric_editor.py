import sys
from pathlib import Path
import unittest

# Add project root to Python path so imports work
sys.path.append(str(Path(__file__).resolve().parent.parent))

from smartscripts.app.teacher.rubric_manager import (
    create_rubric,
    update_rubric,
    get_rubric,
    delete_rubric,
    RubricItem
)


class TestRubricManager(unittest.TestCase):
    def setUp(self):
        # Clear in-memory DB before each test
        from smartscripts.app.teacher import rubric_manager
        rubric_manager.rubrics_db.clear()

    def test_create_and_get_rubric(self):
        rubric_data = {
            "title": "Test Rubric",
            "items": [
                {"criteria": "Accuracy", "max_score": 10},
                {"criteria": "Clarity", "max_score": 5, "description": "How clear is the answer?"}
            ]
        }
        rubric_id = create_rubric(rubric_data)
        loaded = get_rubric(rubric_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None  # for Pylance type safety
        self.assertEqual(loaded["title"], "Test Rubric")
        self.assertEqual(len(loaded["items"]), 2)
        self.assertEqual(loaded["items"][1]["description"], "How clear is the answer?")

    def test_update_rubric(self):
        rubric_data = {
            "title": "Original Rubric",
            "items": [{"criteria": "Accuracy", "max_score": 10}]
        }
        rubric_id = create_rubric(rubric_data)

        update_data = {
            "title": "Updated Rubric",
            "items": [
                {"criteria": "Accuracy", "max_score": 15},
                {"criteria": "Clarity", "max_score": 5}
            ]
        }
        result = update_rubric(rubric_id, update_data)
        self.assertTrue(result)
        loaded = get_rubric(rubric_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None  # for Pylance
        self.assertEqual(loaded["title"], "Updated Rubric")
        self.assertEqual(len(loaded["items"]), 2)
        self.assertEqual(loaded["items"][0]["max_score"], 15)

    def test_delete_rubric(self):
        rubric_data = {
            "title": "To Delete",
            "items": [{"criteria": "Accuracy", "max_score": 10}]
        }
        rubric_id = create_rubric(rubric_data)
        deleted = delete_rubric(rubric_id)
        self.assertTrue(deleted)
        loaded = get_rubric(rubric_id)
        self.assertIsNone(loaded)

    def test_delete_nonexistent_rubric(self):
        self.assertFalse(delete_rubric("nonexistent-id"))


if __name__ == "__main__":
    unittest.main()
