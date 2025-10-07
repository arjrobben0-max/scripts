# tests/test_directory_structure.py

import os
from flask import Flask
from smartscripts.utils.file_helpers import create_test_directory_structure

def test_create_test_directory_structure():
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = os.path.abspath("tmp_uploads")  # temp testing dir

    test_id = 9999  # dummy test ID for testing

    with app.app_context():
        paths = create_test_directory_structure(test_id)

        print("\n📁 Created Directory Structure:")
        for key, path in paths.items():
            exists = os.path.exists(path)
            print(f"{'✅' if exists else '❌'} {key}: {path}")

        assert all(os.path.exists(p) for p in paths.values()), "Some folders were not created."

if __name__ == "__main__":
    test_create_test_directory_structure()
