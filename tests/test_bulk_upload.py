import os
from pathlib import Path
from typing import List, Dict, Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# App entry point — use factory to create app instance
from smartscripts.app import create_app

app = create_app("default")  # or "development" depending on your config
client = TestClient(app)

# OCR / Preprocessing services
from smartscripts.services.ocr_pipeline import (
    ocr_extract_student_info,
    fuzzy_match_student,
    split_pdf_for_student,
    generate_presence_csv,
    run_full_preprocessing
)
from smartscripts.services.ocr_utils import generate_review_zip
from smartscripts.ai.ocr_engine import extract_name_id_from_image

UPLOAD_DIRS = ["uploads/guides", "uploads/rubrics", "uploads/answers"]


# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def sample_class_list(tmp_path) -> List[Dict[str, str]]:
    content = "1023,Amos Kiiza\n1024,Jane Doe\n1025,John Smith\n"
    path = tmp_path / "class_list.csv"
    path.write_text(content)
    return [
        {"id": "1023", "name": "Amos Kiiza"},
        {"id": "1024", "name": "Jane Doe"},
        {"id": "1025", "name": "John Smith"}
    ]


@pytest.fixture
def bulk_test_images() -> List[str]:
    image_paths = [
        "uploads/answers/sample_q1.jpg",
        "uploads/answers/sample_q2.jpg"
    ]
    for path in image_paths:
        if not os.path.exists(path):
            pytest.skip(f"Missing required test image: {path}")
    return image_paths


# -----------------------------
# OCR / Preprocessing Tests
# -----------------------------
def test_extract_name_id(bulk_test_images: List[str]):
    for image_path in bulk_test_images:
        name, student_id = extract_name_id_from_image(image_path)
        result: Dict[str, str] = {"name": name, "id": student_id}
        assert isinstance(result, dict)
        assert "name" in result and "id" in result
        assert isinstance(result["name"], str)
        assert isinstance(result["id"], str)


def test_fuzzy_match(sample_class_list: List[Dict[str, str]]):
    extracted = {"name": "Jane Do", "id": "1024"}
    student_id = extracted.get("id") or ""
    name = extracted.get("name") or ""
    match = fuzzy_match_student(student_id, name, sample_class_list)
    assert match is not None
    if isinstance(match, dict):
        student: Dict[str, str] = match
        assert student.get("name") == "Jane Doe"
        assert student.get("id") == "1024"


def test_ocr_extract_student_info(bulk_test_images: List[str]):
    for image_path in bulk_test_images:
        img = Image.open(image_path)
        name, student_id, confidence = ocr_extract_student_info(img)
        assert isinstance(name, str)
        assert isinstance(student_id, str)
        assert isinstance(confidence, float)


def test_generate_presence_csv(tmp_path, sample_class_list: List[Dict[str, str]]):
    present = [{"name": "Amos Kiiza", "id": "1023", "confidence": 0.95}]
    absent = [{"name": "Jane Doe", "id": "1024", "confidence": 0.0}]
    csv_path = generate_presence_csv(present, absent, test_id=1, output_dir=tmp_path)
    assert csv_path.exists()
    content = csv_path.read_text()
    assert "Amos Kiiza" in content
    assert "Jane Doe" in content


def test_split_pdf_for_student(tmp_path: Path):
    import fitz
    from typing import Any

    pdf_path = tmp_path / "dummy.pdf"
    pdf_doc: Any = fitz.open()
    pdf_doc.new_page(width=595, height=842)  # type: ignore
    pdf_doc.save(str(pdf_path))

    student_pdf_path = split_pdf_for_student(
        pdf_path=pdf_path,
        start_page=0,
        end_page=0,
        student_name="John Smith",
        student_id="1025",
        output_dir=tmp_path
    )
    assert student_pdf_path.exists()


def test_generate_review_zip(tmp_path: Path):
    from smartscripts.models import ExtractedStudentScript

    extracted: List[ExtractedStudentScript] = [ExtractedStudentScript()]
    s = extracted[0]

    # Create dummy PDF file
    dummy_pdf = tmp_path / "dummy1.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")

    # Set attributes safely
    setattr(s, "extracted_pdf_path", str(dummy_pdf))
    setattr(s, "ocr_name", "Amos Kiiza")
    setattr(s, "ocr_student_id", "1023")
    setattr(s, "confidence", 0.9)
    setattr(s, "student_name", "Amos Kiiza")
    setattr(s, "matched_id", "1023")
    setattr(s, "is_confirmed", True)
    setattr(s, "page_count", 1)

    presence_rows = [{"name": "Amos Kiiza", "id": "1023"}, {"name": "Jane Doe", "id": "1024"}]

    zip_output = tmp_path / "review.zip"

    # Convert ExtractedStudentScript objects to dicts
    per_student_dicts = [
        {
            "extracted_pdf_path": s.extracted_pdf_path,
            "ocr_name": s.ocr_name,
            "ocr_student_id": s.ocr_student_id,
            "confidence": s.confidence,
            "student_name": s.student_name,
            "matched_id": s.matched_id,
            "is_confirmed": s.is_confirmed,
            "page_count": s.page_count,
        } for s in extracted
    ]

    zip_path = generate_review_zip(per_student_dicts, presence_rows, str(zip_output))
    assert zip_path.exists()

    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "dummy1.pdf" in names
        assert any("Amos Kiiza" in name for name in names)  # depends on actual zip content


def test_run_full_preprocessing(tmp_path: Path, sample_class_list: List[Dict[str, str]]):
    pdf_path = tmp_path / "bulk_scripts.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")

    result = run_full_preprocessing(pdf_path, test_id=1, class_list=sample_class_list, app=None)
    assert "attendance" in result
    assert "review_zip" in result
    assert Path(result["review_zip"]).exists()
    assert isinstance(result["extracted_scripts"], list)
