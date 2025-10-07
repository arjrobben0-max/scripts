# File: smartscripts/services/ocr_pipeline.py
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
from difflib import SequenceMatcher
from tempfile import NamedTemporaryFile

import fitz  # PyMuPDF
from werkzeug.utils import secure_filename
from PIL import Image
from flask import current_app

from smartscripts.models.extracted_student_script import ExtractedStudentScript
from smartscripts.ai.ocr_engine import extract_name_id_from_image
from smartscripts.ai.text_matching import fuzzy_match_id
from smartscripts.tasks.ocr_tasks import detect_front_pages_opencv
from smartscripts.services.ocr_utils import generate_review_zip  # Canonical ZIP function
from smartscripts.utils.file_helpers import get_uploaded_file_path


# -------------------------------
# OCR Extraction & Student Matching
# -------------------------------
def ocr_extract_student_info(page_image: Image.Image) -> Tuple[str, str, float]:
    """Extract student name and ID from a single PIL Image using OCR."""
    with NamedTemporaryFile(suffix=".png") as tmp:
        page_image.save(tmp.name)
        try:
            result = extract_name_id_from_image(tmp.name)
            if not isinstance(result, (list, tuple)):
                result = ("", "", 0.0)
        except Exception:
            result = ("", "", 0.0)

        if len(result) == 3:
            name, student_id, confidence = result
        elif len(result) == 2:
            name, student_id = result
            confidence = 0.0
        else:
            name, student_id, confidence = "", "", 0.0

    return (name or "").strip(), (student_id or "").strip(), confidence


def fuzzy_match_student(student_id: str, name: str, class_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Match OCR results to class list by ID first, then by name similarity."""
    if student_id:
        match_id, _ = fuzzy_match_id(student_id, [s["id"] for s in class_list])
        if match_id:
            return next((s for s in class_list if s["id"] == match_id), None)

    if name:
        best_score = 0.0
        best_match = None
        for s in class_list:
            score = SequenceMatcher(None, name.lower(), s["name"].lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = s
        if best_score >= 0.8:
            return best_match
    return None


# -------------------------------
# PDF Handling
# -------------------------------
def split_pdf_for_student(pdf_path: Path, start_page: int, end_page: int,
                          student_name: str, student_id: str,
                          output_dir: Path) -> Path:
    """Extract a range of pages from the combined PDF and save per student."""
    pdf = fitz.open(pdf_path)
    student_pdf = fitz.open()
    for p in range(start_page, end_page + 1):
        student_pdf.insert_pdf(pdf, from_page=p, to_page=p)

    safe_name = secure_filename(student_name or "unknown")
    safe_id = secure_filename(student_id or "unknown")
    filename = f"{uuid4().hex}_{safe_id}-{safe_name}.pdf"
    output_path = output_dir / filename
    student_pdf.save(str(output_path))
    return output_path


# -------------------------------
# Attendance CSV
# -------------------------------
def generate_presence_csv(present: List[Dict[str, Any]], absent: List[Dict[str, Any]],
                          test_id: int, output_dir: Path) -> Path:
    """Generate a CSV file containing attendance information."""
    csv_path = output_dir / f"attendance_test_{test_id}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Status", "Name", "ID", "Confidence"])
        for s in present:
            writer.writerow(["Present", s.get("name", ""), s.get("id", ""), s.get("confidence", 0.0)])
        for s in absent:
            writer.writerow(["Absent", s.get("name", ""), s.get("id", ""), s.get("confidence", 0.0)])
    return csv_path


# -------------------------------
# Full Preprocessing Pipeline
# -------------------------------
def run_full_preprocessing(combined_pdf_path: Path, test_id: int,
                           class_list: Optional[List[Dict[str, Any]]] = None,
                           app=None) -> Dict[str, Any]:
    """
    Run full OCR, student matching, PDF splitting, and review ZIP creation.
    Returns attendance info, ZIP path, and extracted scripts list.
    """
    if class_list is None:
        class_list = []
    if app is None:
        app = current_app

    upload_dir = Path(app.root_path) / "static" / "uploads" / str(test_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    from pdf2image import convert_from_path
    images = convert_from_path(str(combined_pdf_path), dpi=300)
    front_pages = detect_front_pages_opencv(images)

    extracted_student_scripts: List[ExtractedStudentScript] = []
    attendance = {"present": [], "absent": []}

    for start, end in front_pages:
        page_image = images[start]
        name, student_id, confidence = ocr_extract_student_info(page_image)
        matched = fuzzy_match_student(student_id, name, class_list)

        if matched:
            attendance["present"].append({
                "name": matched["name"],
                "id": matched["id"],
                "confidence": confidence
            })
        else:
            attendance["absent"].append({
                "name": name,
                "id": student_id,
                "confidence": confidence
            })

        student_pdf_path = split_pdf_for_student(
            pdf_path=combined_pdf_path,
            start_page=start,
            end_page=end,
            student_name=matched["name"] if matched else name,
            student_id=matched["id"] if matched else student_id,
            output_dir=upload_dir
        )

        # Assign ORM fields
        student_script = ExtractedStudentScript()
        student_script.extracted_pdf_path = str(student_pdf_path.relative_to(upload_dir.parent.parent))
        student_script.ocr_name = name
        student_script.ocr_student_id = student_id
        student_script.confidence = confidence
        student_script.student_name = matched["name"] if matched else name
        student_script.matched_id = matched["id"] if matched else student_id
        student_script.is_confirmed = bool(matched)
        student_script.page_count = end - start + 1

        extracted_student_scripts.append(student_script)

    presence_csv = generate_presence_csv(attendance["present"], attendance["absent"], test_id, upload_dir)

    # -------------------------------
    # FIXED: Corrected call to generate_review_zip
    # -------------------------------
    review_zip_path = generate_review_zip(
        per_student_files=[
            {
                "pdf_path": get_uploaded_file_path(s.extracted_pdf_path),
                "name": s.student_name,
                "id": s.matched_id,
                "confidence": s.confidence
            }
            for s in extracted_student_scripts if s.extracted_pdf_path
        ],
        presence_rows=[{**s} for s in attendance["present"] + attendance["absent"]],
        zip_path=str(upload_dir / f"review_test_{test_id}.zip")
    )

    return {
        "attendance": attendance,
        "review_zip": str(review_zip_path),
        "extracted_student_scripts": extracted_student_scripts
    }
