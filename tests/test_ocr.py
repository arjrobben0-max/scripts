import os
import shutil
from pathlib import Path
from typing import Dict, Tuple, List
from PyPDF2 import PdfReader

# Ensure smartscripts/ is in sys.path if running directly
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from smartscripts.ai.ocr_engine import extract_text_from_image
from smartscripts.tasks.ocr_tasks import detect_front_page, fuzzy_match_student_id
from smartscripts.services.ocr_helpers import rename_student_pdfs
from smartscripts.services.file_manager import split_pdf_by_student

# ─── Test paths ──────────────────────────────────────────
TEST_UPLOAD_DIR = Path("tests/test_uploads")
OUTPUT_DIR = Path("tests/test_output")
CLASS_LIST_CSV = Path("tests/class_list.csv")

# ─── Fixtures ───────────────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def setup_dirs():
    TEST_UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    yield
    shutil.rmtree(TEST_UPLOAD_DIR)
    shutil.rmtree(OUTPUT_DIR)

# ─── Tests ──────────────────────────────────────────────
@pytest.mark.parametrize("pdf_file", ["sample_test.pdf"])
def test_preprocessing_pipeline(pdf_file):
    """
    Full pipeline test using updated file_manager.split_pdf_by_student:
    1. Detect front pages
    2. OCR Name & ID (TrOCR + Tesseract fallback)
    3. Fuzzy match IDs
    4. Split PDFs
    5. Rename per-student PDFs
    """
    pdf_path = TEST_UPLOAD_DIR / pdf_file
    assert pdf_path.exists(), f"Test PDF not found: {pdf_path}"

    # --- Step 1: Front Page Detection ---
    raw_front_pages = detect_front_page(pdf_path)
    front_pages: Dict[int, Path] = {k: v if isinstance(v, Path) else v[0] for k, v in raw_front_pages.items()}
    assert front_pages, "At least one front page should be detected"

    # --- Step 2: OCR Extraction ---
    ocr_results: Dict[int, str] = {}
    for page_num, img_path in front_pages.items():
        text = extract_text_from_image(img_path)
        if not text.strip():
            text = extract_text_from_image(img_path)  # fallback
        assert text.strip(), f"OCR failed on page {page_num}"
        ocr_results[page_num] = text

    # --- Step 3: Load class list ---
    class_list: List[Dict[str, str]] = []
    if CLASS_LIST_CSV.exists():
        import csv
        with open(CLASS_LIST_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            class_list = [row for row in reader]
    else:
        pytest.skip(f"Class list CSV not found: {CLASS_LIST_CSV}")

    # --- Step 4: Split PDF by student ---
    student_scripts = split_pdf_by_student(
        combined_pdf_path=str(pdf_path),
        test_id=1,
        class_list=class_list
    )
    assert student_scripts, "No student scripts returned from split_pdf_by_student"

    # --- Step 5: Rename PDFs ---
    # Extract the generated PDF paths
    pdf_paths = [Path(script["extracted_pdf_path"]) for script in student_scripts if script.get("extracted_pdf_path")]
    renamed_pdfs = rename_student_pdfs(
        student_pdfs=pdf_paths,
        student_map={i: (script["ocr_student_id"], script["ocr_name"]) for i, script in enumerate(student_scripts)},
        output_dir=OUTPUT_DIR
    )

    for path in renamed_pdfs:
        assert path.exists(), f"Renamed PDF not found: {path}"
        reader = PdfReader(str(path))
        assert len(reader.pages) > 0, f"PDF {path} has no pages"

# ─── Run as script ──────────────────────────────────────
if __name__ == "__main__":
    pytest.main([__file__])
