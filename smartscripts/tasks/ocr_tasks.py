"""
OCR Tasks
---------
Handles:
 - PDF → Image conversion
 - Front-page detection
 - OCR via TrOCR or Tesseract
 - Student ID/name extraction
 - Class list fuzzy matching
 - Attendance summary
"""

import io
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple, Union, Any

from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes, convert_from_path
from PIL import Image
import pytesseract
import numpy as np
import cv2
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel, logging as transformers_logging
from thefuzz import process
from flask import current_app, has_app_context
from celery import current_task
from celery.exceptions import Ignore

# ✅ Import global Celery instance
from smartscripts.extensions import celery

# ───────────────────────────────────────────────────────────────
# Suppress HuggingFace warnings
# ───────────────────────────────────────────────────────────────
transformers_logging.set_verbosity_error()

# ───────────────────────────────────────────────────────────────
# Lazy-loaded TrOCR
# ───────────────────────────────────────────────────────────────
_trocr: Dict[str, Union[None, TrOCRProcessor, VisionEncoderDecoderModel, torch.device]] = {
    "processor": None,
    "model": None,
    "device": None
}

def _load_trocr() -> Tuple[TrOCRProcessor, VisionEncoderDecoderModel, torch.device]:
    """Lazy-load TrOCR model and processor."""
    if _trocr["model"] is None or _trocr["processor"] is None:
        processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
        model = VisionEncoderDecoderModel.from_pretrained(
            "microsoft/trocr-base-handwritten",
            ignore_mismatched_sizes=True
        )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        _trocr.update({"processor": processor, "model": model, "device": device})
    return _trocr["processor"], _trocr["model"], _trocr["device"]

# ───────────────────────────────────────────────────────────────
# OCR Functions
# ───────────────────────────────────────────────────────────────
def ocr_trocr(image: Image.Image) -> str:
    """Run TrOCR on an image."""
    processor, model, device = _load_trocr()
    try:
        pixel_values = processor(images=[image], return_tensors="pt").pixel_values.to(device)
        generated_ids = model.generate(pixel_values)
        return processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    except Exception as e:
        if has_app_context():
            current_app.logger.warning(f"[ocr_trocr] Failed: {e}")
        return ""

def ocr_tesseract(image: Image.Image) -> str:
    """Fallback OCR using Tesseract."""
    try:
        return pytesseract.image_to_string(image)
    except Exception as e:
        if has_app_context():
            current_app.logger.warning(f"[ocr_tesseract] Failed: {e}")
        return ""

# ───────────────────────────────────────────────────────────────
# Fuzzy Matching
# ───────────────────────────────────────────────────────────────
def fuzzy_match_student_id(extracted_id: str, class_list: List[str]) -> Tuple[Union[str, None], float]:
    """
    Fuzzy match a student ID against a class list.
    Returns a tuple: (matched_id, score)
    If no match is found, returns (None, 0.0)
    """
    if not extracted_id or not class_list:
        return None, 0.0

    result = process.extractOne(extracted_id, class_list)
    if result is None:
        return None, 0.0

    match, score = result
    return match, score / 100.0  # normalize score to 0–1

# ───────────────────────────────────────────────────────────────
# PDF Helpers
# ───────────────────────────────────────────────────────────────
def page_to_image(pdf_page) -> Image.Image:
    """Convert a single PDF page to a PIL image."""
    pdf_bytes = io.BytesIO()
    writer = PdfWriter()
    writer.add_page(pdf_page)
    writer.write(pdf_bytes)
    images = convert_from_bytes(pdf_bytes.getvalue())
    return images[0]

def save_student_pdf(original_pdf_path: Path, page_number: int, student_id: str, student_name: str, output_dir: Path) -> str:
    """Save a student's single-page PDF."""
    reader = PdfReader(original_pdf_path)
    page = reader.pages[page_number - 1]
    writer = PdfWriter()
    writer.add_page(page)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{student_id or 'unknown'}-{student_name or 'unknown'}.pdf"
    pdf_path = output_dir / filename
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return str(pdf_path)

# ───────────────────────────────────────────────────────────────
# Front-page Detection
# ───────────────────────────────────────────────────────────────
def detect_front_page(image: Image.Image, return_confidence: bool = False) -> Union[Image.Image, Tuple[Image.Image, float]]:
    """Detect and crop the front page area."""
    try:
        img = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return (image, 0.0) if return_confidence else image

        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        cropped = img[y:y + h, x:x + w]
        non_zero = cv2.countNonZero(cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY))
        confidence = non_zero / (cropped.shape[0] * cropped.shape[1])
        cropped_image = Image.fromarray(cropped)
        return (cropped_image, confidence) if return_confidence else cropped_image
    except Exception as e:
        if has_app_context():
            current_app.logger.warning(f"[detect_front_page] Failed: {e}")
        return (image, 0.0) if return_confidence else image

def detect_front_pages_opencv(images: List[Image.Image]) -> List[Tuple[int, int]]:
    """Detect front pages across all images."""
    front_pages = []
    for idx, img in enumerate(images):
        _, conf = detect_front_page(img, return_confidence=True)
        if conf > 0.3:  # slightly higher threshold for reliability
            front_pages.append(idx)
    ranges = []
    for i, start_idx in enumerate(front_pages):
        end_idx = front_pages[i + 1] - 1 if i + 1 < len(front_pages) else len(images) - 1
        ranges.append((start_idx, end_idx))
    return ranges

# ───────────────────────────────────────────────────────────────
# OCR Text Extraction
# ───────────────────────────────────────────────────────────────
def extract_student_id_name(ocr_text: str) -> Tuple[str, str, float]:
    """Extract student ID and name from OCR text."""
    if not ocr_text:
        return "unknown", "unknown", 0.0
    name_match = re.search(r"name[:\s]+([A-Za-z\s\-\']+)", ocr_text, flags=re.I)
    id_match = re.search(r"id[:\s]+([A-Za-z0-9\-]+)", ocr_text, flags=re.I)
    name = name_match.group(1).strip() if name_match else "unknown"
    student_id = id_match.group(1).strip() if id_match else "unknown"
    conf = 0.5 * bool(name_match) + 0.5 * bool(id_match)
    return student_id, name, conf

# ───────────────────────────────────────────────────────────────
# Celery Task with Progress & Safe Exception Handling
# ───────────────────────────────────────────────────────────────
@celery.task(bind=True, name="smartscripts.tasks.ocr_tasks.run_student_script_ocr_pipeline")
def run_student_script_ocr_pipeline(self, test_id: int, pdf_path: str, class_list_path: str) -> Dict[str, Any]:
    """Full OCR pipeline with progress tracking, safe exception handling for Celery backend."""
    try:
        # Step 1: Load class list
        with open(class_list_path, newline="", encoding="utf-8") as f:
            class_list = [row.get("id") for row in csv.DictReader(f)]
        self.update_state(state="STARTED", meta={"percent": 10})

        # Step 2: Convert PDF to images
        images = convert_from_path(pdf_path, dpi=300)
        total_pages = len(images)
        self.update_state(state="STARTED", meta={"percent": 20})

        # Step 3: Detect front pages
        front_pages = detect_front_pages_opencv(images)
        if not front_pages:
            front_pages = [(0, total_pages - 1)]
        self.update_state(state="STARTED", meta={"percent": 30})

        # Step 4: OCR each front page
        attendance = {"present": [], "absent": []}
        results = []
        for i, (start, end) in enumerate(front_pages):
            page_img = images[start]

            # ✅ TrOCR first, fallback to Tesseract
            ocr_text = ocr_trocr(page_img)
            if not ocr_text.strip():
                ocr_text = ocr_tesseract(page_img)

            student_id, name, conf = extract_student_id_name(ocr_text)
            matched_id, score = fuzzy_match_student_id(student_id, class_list)

            entry = {"start_page": start, "end_page": end, "student_id": student_id, "name": name, "confidence": conf}
            results.append(entry)

            if score > 0.8:
                attendance["present"].append({"name": name, "id": matched_id, "confidence": conf})
            else:
                attendance["absent"].append({"name": name, "id": student_id, "confidence": conf})

            # Update progress per front page
            percent_complete = 30 + int(((i + 1) / len(front_pages)) * 70)
            current_task.update_state(state="STARTED", meta={"percent": percent_complete})

        # Step 5: Done
        self.update_state(state="SUCCESS", meta={"percent": 100})
        return {"status": "COMPLETED", "percent": 100, "attendance": attendance, "results": results}

    except Exception as e:
        if has_app_context():
            current_app.logger.error(f"[OCR] Task failed: {type(e).__name__}: {e}")

        error_info = {"type": type(e).__name__, "message": str(e)}
        self.update_state(state="FAILURE", meta={"percent": 0, "error": error_info})

        raise Ignore()
