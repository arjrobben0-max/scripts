# smartscripts/tasks/ocr_tasks.py
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
from thefuzz import process  # fixed import
from flask import current_app, has_app_context

from smartscripts.extensions import celery  # type: ignore

# ----------------------------
# Suppress HuggingFace warnings
# ----------------------------
transformers_logging.set_verbosity_error()

# ----------------------------
# Lazy-loaded TrOCR
# ----------------------------
_trocr: Dict[str, Union[None, TrOCRProcessor, VisionEncoderDecoderModel, torch.device]] = {
    "processor": None,
    "model": None,
    "device": None
}

def _load_trocr() -> Tuple[TrOCRProcessor, VisionEncoderDecoderModel, torch.device]:
    """
    Lazy load TrOCR processor and model.
    """
    if _trocr["model"] is None or _trocr["processor"] is None:
        processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
        model = VisionEncoderDecoderModel.from_pretrained(
            "microsoft/trocr-base-handwritten",
            ignore_mismatched_sizes=True
        )
        device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)  # type: ignore
        _trocr["processor"] = processor  # type: ignore
        _trocr["model"] = model  # type: ignore
        _trocr["device"] = device  # type: ignore
    return _trocr["processor"], _trocr["model"], _trocr["device"]  # type: ignore

# ----------------------------
# OCR Functions
# ----------------------------
def ocr_trocr(image: Image.Image) -> str:
    """
    OCR using TrOCR (handwritten).
    """
    processor, model, device = _load_trocr()
    if processor is None or model is None or device is None:
        return ""

    try:
        images_list: List[Image.Image] = [image]  # ensure list
        pixel_values = processor(images=images_list, return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(device)  # type: ignore
        generated_ids = model.generate(pixel_values)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return text
    except Exception as e:
        if has_app_context():
            current_app.logger.warning(f"[ocr_trocr] Failed: {e}")
        return ""

def ocr_tesseract(image: Image.Image) -> str:
    """
    OCR fallback using Tesseract.
    """
    try:
        return pytesseract.image_to_string(image)
    except Exception as e:
        if has_app_context():
            current_app.logger.warning(f"[ocr_tesseract] Failed: {e}")
        return ""

def fuzzy_match_student_id(extracted_id: str, class_list: List[str]) -> Tuple[str, float]:
    """
    Fuzzy match a student ID to the class list.
    Returns (best_match, confidence_score_0to1)
    """
    extracted_id = str(extracted_id or "")
    if not class_list:
        return extracted_id or "unknown", 0.0
    match, score = process.extractOne(extracted_id, class_list)
    return match, score / 100.0

# ----------------------------
# PDF Helpers
# ----------------------------
def page_to_image(pdf_page) -> Image.Image:
    pdf_bytes = io.BytesIO()
    writer = PdfWriter()
    writer.add_page(pdf_page)
    writer.write(pdf_bytes)
    images = convert_from_bytes(pdf_bytes.getvalue())
    return images[0]

def save_student_pdf(original_pdf_path: Path, page_number: int, student_id: str, student_name: str, output_dir: Path) -> str:
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

# ----------------------------
# Front-page Detection
# ----------------------------
def detect_front_page(image: Image.Image, return_confidence: bool = False) -> Union[Image.Image, Tuple[Image.Image, float]]:
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
    front_pages = []
    for idx, img in enumerate(images):
        _, conf = detect_front_page(img, return_confidence=True)
        if conf > 0.2:
            front_pages.append(idx)
    ranges = []
    for i, start_idx in enumerate(front_pages):
        end_idx = front_pages[i + 1] - 1 if i + 1 < len(front_pages) else len(images) - 1
        ranges.append((start_idx, end_idx))
    return ranges

# ----------------------------
# OCR Text Extraction
# ----------------------------
def extract_student_id_name(ocr_text: str) -> Tuple[str, str, float]:
    if not ocr_text:
        return "unknown", "unknown", 0.0
    name_match = re.search(r"name[:\s]+([A-Za-z\s\-\']+)", ocr_text, flags=re.I)
    id_match = re.search(r"id[:\s]+([A-Za-z0-9\-]+)", ocr_text, flags=re.I)
    name = name_match.group(1).strip() if name_match else "unknown"
    student_id = id_match.group(1).strip() if id_match else "unknown"
    conf = 0.0
    if name_match:
        conf += 0.5
    if id_match:
        conf += 0.5
    return student_id, name, conf

# ----------------------------
# Celery Task
# ----------------------------
@celery.task(name="run_student_script_ocr_pipeline")
def run_student_script_ocr_pipeline(test_id: int, pdf_path: str, class_list_path: str) -> Dict[str, Any]:
    """
    OCR pipeline:
    - Convert PDF to images
    - Detect front pages
    - Extract student IDs and names
    - Fuzzy match to class list
    - Return attendance & results
    """
    # Load class list
    class_list: List[Dict[str, str]] = []
    try:
        with open(class_list_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            class_list = list(reader)
    except Exception as e:
        if has_app_context():
            current_app.logger.warning(f"Failed to read class list: {e}")

    images: List[Image.Image] = convert_from_path(pdf_path, dpi=300)
    front_pages: List[Tuple[int, int]] = detect_front_pages_opencv(images)

    attendance: Dict[str, List[Dict[str, Union[str, float]]]] = {"present": [], "absent": []}
    results: List[Dict[str, Union[int, str, float]]] = []

    for start, end in front_pages:
        page_img = images[start]
        student_id, name, conf = extract_student_id_name(ocr_tesseract(page_img))
        matched_id, score = fuzzy_match_student_id(student_id, [s["id"] for s in class_list])
        if score > 0.8:
            attendance["present"].append({"name": name, "id": matched_id, "confidence": conf})
        else:
            attendance["absent"].append({"name": name, "id": student_id, "confidence": conf})
        results.append({
            "start_page": start,
            "end_page": end,
            "student_id": student_id,
            "name": name,
            "confidence": conf,
        })

    return {"attendance": attendance, "results": results}
