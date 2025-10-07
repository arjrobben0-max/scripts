import io
import os
import pytest
from flask import url_for
from werkzeug.datastructures import FileStorage
from app import create_app, db
from app.models import Test

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    return app.test_client()

def create_pdf_file(filename="file.pdf"):
    pdf_bytes = b"%PDF-1.4 dummy pdf content"
    return FileStorage(stream=io.BytesIO(pdf_bytes), filename=filename, content_type="application/pdf")

def login_teacher(client):
    return client.post('/login', data=dict(username='teacher1', password='password'), follow_redirects=True)

# -----------------------------
# Upload Page & Base Uploads
# -----------------------------

def test_get_upload_page(client):
    response = client.get("/uploads/upload_test_materials")
    assert response.status_code == 200
    assert b"Enter test title" in response.data

def test_successful_upload(client, tmp_path, app):
    data = {
        "test_title": "Midterm Test",
        "marking_guide": create_pdf_file("guide.pdf"),
        "rubric": create_pdf_file("rubric.pdf"),
        "answered_script": create_pdf_file("answered.pdf"),
        "student_scripts": [create_pdf_file("student1.pdf"), create_pdf_file("student2.pdf")]
    }

    # Configure upload directories
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    app.config["UPLOAD_FOLDER_GUIDES"] = os.path.join(str(tmp_path), "guides")
    app.config["UPLOAD_FOLDER_RUBRICS"] = os.path.join(str(tmp_path), "rubrics")
    os.makedirs(app.config["UPLOAD_FOLDER_GUIDES"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER_RUBRICS"], exist_ok=True)

    multipart_data = {
        "test_title": data["test_title"],
        "marking_guide": (data["marking_guide"].stream, data["marking_guide"].filename),
        "rubric": (data["rubric"].stream, data["rubric"].filename),
        "answered_script": (data["answered_script"].stream, data["answered_script"].filename),
        "student_scripts": [
            (s.stream, s.filename) for s in data["student_scripts"]
        ]
    }

    response = client.post("/uploads/upload_test_materials", data=multipart_data, content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert b"Upload successful" in response.data

    guides_path = os.path.join(app.config["UPLOAD_FOLDER_GUIDES"], "Midterm_Test_marking_guide.pdf")
    rubrics_path = os.path.join(app.config["UPLOAD_FOLDER_RUBRICS"], "Midterm_Test_rubric.pdf")
    answers_path = os.path.join(app.config["UPLOAD_FOLDER"], "Midterm_Test", "answered_script.pdf")
    submissions_path = os.path.join(app.config["UPLOAD_FOLDER"], "Midterm_Test", "student_scripts")
    assert os.path.isfile(guides_path)
    assert os.path.isfile(rubrics_path)
    assert os.path.isfile(answers_path)
    assert os.path.isdir(submissions_path)
    assert len(os.listdir(submissions_path)) == 2

def test_invalid_file_type(client):
    txt_file = FileStorage(stream=io.BytesIO(b"not a pdf"), filename="invalid.txt", content_type="text/plain")
    multipart_data = {
        "test_title": "Test",
        "marking_guide": (txt_file.stream, txt_file.filename),
        "rubric": (create_pdf_file("rubric.pdf").stream, "rubric.pdf"),
        "answered_script": (create_pdf_file("answered.pdf").stream, "answered.pdf"),
        "student_scripts": [(create_pdf_file("student1.pdf").stream, "student1.pdf")]
    }
    response = client.post("/uploads/upload_test_materials", data=multipart_data, content_type="multipart/form-data")
    assert b"Invalid file type" in response.data or b"pdf" in response.data.lower()
