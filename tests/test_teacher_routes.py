# tests/test_teacher_routes.py
from __future__ import annotations
import sys
from pathlib import Path
import io

import pytest
from flask.testing import FlaskClient

# Ensure project root is in PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parent.parent))

from smartscripts.app import create_app
from smartscripts.extensions import db

# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture(scope="session")
def app():
    """Create a Flask app configured for testing."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def client(app) -> FlaskClient:
    """Test client for HTTP requests."""
    return app.test_client()


@pytest.fixture()
def sample_user(app):
    """Create a sample teacher user."""
    from smartscripts.models.user import User
    user = User(
        username="teacher1",
        email="teacher1@example.com",
        password="password",
        role="teacher"
    )
    user.is_admin = True
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def login_client(client: FlaskClient, sample_user):
    """Log in the sample user."""
    response = client.post(
        "/teacher/login",
        data={
            "username": sample_user.username,
            "password": "password"
        },
        follow_redirects=True
    )
    assert response.status_code in (200, 302)
    return client


@pytest.fixture()
def sample_test(app, sample_user):
    """Create a dummy test record."""
    from smartscripts.models.test import Test
    test = Test(title="Sample Test", subject="Physics", teacher_id=sample_user.id)
    db.session.add(test)
    db.session.commit()
    return test


# -----------------------------
# Helper function for file upload
# -----------------------------
def upload_dummy_file(
    client: FlaskClient,
    test_id: int,
    file_type: str,
    filename="dummy.txt",
    content=b"hello world"
):
    data = {
        "file": (io.BytesIO(content), filename)
    }
    return client.post(
        f"/teacher/upload_file/{test_id}/{file_type}",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True
    )


# -----------------------------
# Tests
# -----------------------------
def test_login_register_logout(client: FlaskClient):
    # Login page
    response = client.get("/teacher/login")
    assert response.status_code == 200

    # Register page
    response = client.get("/teacher/register")
    assert response.status_code == 200

    # Logout page (redirects)
    response = client.get("/teacher/logout")
    assert response.status_code in (302, 200)


def test_dashboard_and_ai_marking(login_client: FlaskClient, sample_test):
    response = login_client.get("/teacher/dashboard")
    assert response.status_code == 200

    # Start AI marking (POST or GET depending on route)
    response = login_client.get(f"/teacher/start_ai_marking/{sample_test.id}")
    assert response.status_code in (200, 302)

    # Export submissions (dummy)
    response = login_client.get(f"/teacher/export_submissions/{sample_test.id}?format=pdf")
    assert response.status_code in (200, 302)


def test_review_submission(login_client: FlaskClient, sample_test):
    response = login_client.get(f"/teacher/review_submission/{sample_test.id}")
    assert response.status_code in (200, 302)


def test_delete_routes(login_client: FlaskClient, sample_test):
    endpoints = [
        f"/teacher/delete_test/{sample_test.id}",
        f"/teacher/delete_file/{sample_test.id}/answers",
        f"/teacher/delete_all_submissions/{sample_test.id}"
    ]
    for endpoint in endpoints:
        response = login_client.post(endpoint, follow_redirects=True)
        assert response.status_code in (200, 302)


def test_download_routes(login_client: FlaskClient, sample_test):
    file_types = [
        "question_paper", "rubric", "marking_guide", "answered_script",
        "class_list", "combined_scripts", "student_list", "review_zip", "all_files"
    ]
    for file_type in file_types:
        response = login_client.get(f"/teacher/download_{file_type}/{sample_test.id}")
        # Might redirect if file missing
        assert response.status_code in (200, 302, 404)


def test_file_routes(login_client: FlaskClient, sample_test):
    # Start OCR
    response = login_client.post(f"/teacher/start_ocr/{sample_test.id}")
    assert response.status_code in (200, 302)

    # OCR progress
    response = login_client.get("/teacher/ocr_progress/dummy_task_id")
    assert response.status_code in (200, 302)

    # Preprocess summary
    response = login_client.get(f"/teacher/preprocess_summary/{sample_test.id}")
    assert response.status_code in (200, 302)

    # Export zip
    response = login_client.get(f"/teacher/export_zip/{sample_test.id}")
    assert response.status_code in (200, 302)


def test_manage_routes(login_client: FlaskClient, sample_test):
    # Manage test files
    response = login_client.get(f"/teacher/manage_test_files/{sample_test.id}")
    assert response.status_code in (200, 302)

    # Upload dummy file
    resp = upload_dummy_file(login_client, sample_test.id, "answers")
    assert resp.status_code in (200, 302)

    # Delete file
    response = login_client.post(f"/teacher/delete_file/{sample_test.id}/answers", follow_redirects=True)
    assert response.status_code in (200, 302)

    # Start preprocessing
    response = login_client.post(f"/teacher/start_preprocessing/{sample_test.id}", follow_redirects=True)
    assert response.status_code in (200, 302)

    # Task control (pause/resume/cancel/status)
    for action in ["pause_task", "resume_task", "cancel_task", "task_status"]:
        response = login_client.post(f"/teacher/{action}/dummy_task", follow_redirects=True)
        assert response.status_code in (200, 302)
