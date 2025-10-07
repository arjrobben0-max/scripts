# File: tests/test_pdf_generation.py

import shutil
from pathlib import Path
from typing import List

import pytest
from PyPDF2 import PdfReader

from smartscripts.app import create_app
from smartscripts.generate_pdf import create_pdf_report
from smartscripts.services.ocr_helpers import (
    rename_student_pdfs,
    safe_extract_name_id,
    detect_student_front_pages,
)
from smartscripts.services.analytics_service import generate_presence_table
from smartscripts.services.file_manager import split_pdf_by_student
from smartscripts.app.teacher.utils import parse_class_list, match_name_id_to_classlist

app = create_app("testing")
TMP_DIR = Path("tests/tmp_pdf")


@pytest.fixture(scope="module", autouse=True)
def setup_dirs():
    TMP_DIR.mkdir(exist_ok=True)
    yield
    shutil.rmtree(TMP_DIR)


@pytest.fixture
def sample_class_list(tmp_path) -> str:
    path = tmp_path / "class_list.csv"
    path.write_text("1023,Amos Kiiza\n1024,Jane Doe\n1025,John Smith\n")
    return str(path)


@pytest.fixture
def sample_images(tmp_path) -> List[Path]:
    paths = []
    for i in range(2):
        path = tmp_path / f"page_{i+1}.jpg"
        path.write_bytes(b"fake-image-content")
        paths.append(path)
    return paths


@pytest.fixture
def sample_pdf(tmp_path) -> str:
    path = tmp_path / "test.pdf"
    path.write_bytes(b"%PDF-1.4 dummy pdf content with pages")
    return str(path)


def test_pdf_report_creation(tmp_path):
    student_name = "John Doe"
    guide_name = "Business Ethics"
    question_scores = {
        "Q1": {"score": 80, "feedback": "Good explanation, missed one point."},
        "Q2": {"score": 90, "feedback": "Well done."},
        "Q3": {"score": 70, "feedback": "Need more clarity."},
    }
    total_score = 80.0
    annotated_img = "tests/sample_data/john_doe_q1.png"  # ensure file exists

    output_path = tmp_path / "john_doe_report.pdf"
    create_pdf_report(
        student_name,
        guide_name,
        question_scores,
        total_score,
        output_path=str(output_path),
        annotated_img_path=annotated_img,
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_full_preprocessing_pipeline(sample_images, sample_pdf, sample_class_list):
    # Detect student page ranges
    page_ranges = detect_student_front_pages(sample_images)
    assert len(page_ranges) > 0

    # OCR extraction
    ocr_results = {}
    for start, end in page_ranges:
        for idx in range(start, end + 1):
            image_path = sample_images[idx]
            name, student_id, confidence = safe_extract_name_id(image_path)
            assert isinstance(name, str)
            assert isinstance(student_id, str)
            assert 0.0 <= confidence <= 1.0
            ocr_results[image_path] = {
                "name": name,
                "id": student_id,
                "confidence": confidence,
            }

    # Fuzzy match to class list
    classlist = parse_class_list(sample_class_list)
    matched_results = {}
    for image_path, data in ocr_results.items():
        match, conf = match_name_id_to_classlist(data, classlist)
        if match:
            matched_results[image_path] = {
                "student_id": match.get("id", ""),
                "name": match.get("name", ""),
                "confidence": conf,
            }

    # Generate presence table
    presence_table = generate_presence_table(list(matched_results.values()), classlist)
    assert len(presence_table) == len(classlist)
    present_ids = [entry["student_id"] for entry in presence_table if entry.get("present")]
    for res in matched_results.values():
        assert res["student_id"] in present_ids

    # Split PDF and rename
    student_pdfs_info = split_pdf_by_student(
        combined_pdf_path=sample_pdf,
        test_id=1,
        class_list=classlist,
    )

    renamed_pdfs_info = rename_student_pdfs(
        student_map=student_pdfs_info,
        output_dir=TMP_DIR
    )
    for p_info in renamed_pdfs_info:
        path_obj = Path(p_info["output_path"])
        assert path_obj.exists()
        reader = PdfReader(str(path_obj))
        assert len(reader.pages) > 0


def test_ocr_fallback_and_confidence(sample_images):
    for image in sample_images:
        name, student_id, confidence = safe_extract_name_id(image)
        assert isinstance(name, str)
        assert isinstance(student_id, str)
        assert 0.0 <= confidence <= 1.0
