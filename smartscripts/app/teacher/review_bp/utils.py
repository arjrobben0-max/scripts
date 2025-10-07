from __future__ import annotations
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from io import BytesIO

import cv2
import numpy as np
from PIL import Image
import pytesseract
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from flask import url_for, current_app
from flask_login import current_user

# type: ignore for optional library fixes
try:
    import pandas as pd  # type: ignore
    from thefuzz import process  # type: ignore
except ImportError:
    current_app.logger.warning("pandas or thefuzz not installed; fuzzy matching will fail.")

from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path

from smartscripts.extensions import db
from smartscripts.models import Test, OCRSubmission, AuditLog

AUDIT_FIELD_OCR_NAME = "OCR_NAME"
AUDIT_FIELD_OCR_ID = "OCR_ID"

# -----------------------------
# File / URL Helpers
# -----------------------------
def file_url(filename: Optional[str]) -> Optional[str]:
    return url_for("file_routes_bp.uploaded_file", filename=filename) if filename else None


def is_teacher_or_admin(test: Test) -> bool:
    return test.teacher_id == current_user.id or current_user.is_admin


def get_urls_for_guide(test_id: int) -> Dict[str, str]:
    try:
        return {
            "review": url_for("review_bp.review_test", test_id=test_id),
            "submissions": url_for("review_bp.list_submissions", test_id=test_id),
            "analytics": url_for("analytics_bp.test_dashboard", test_id=test_id),
        }
    except Exception as e:
        current_app.logger.warning(f"[get_urls_for_guide] Failed: {e}")
        return {}


# -----------------------------
# OCR Override Helpers
# -----------------------------
def apply_ocr_override(sub: OCRSubmission, name: str, stud_id: str) -> bool:
    changed = False

    if name and name != sub.corrected_name:
        db.session.add(
            AuditLog(
                event_type="OCR_OVERRIDE_NAME",
                user_id=current_user.id,
                test_id=sub.test_id,
                ocr_submission_id=sub.id,
                student_id=sub.corrected_id,
                original_name=sub.corrected_name,
                corrected_name=name,
                description=f"Corrected name from '{sub.corrected_name}' to '{name}'"
            )
        )
        sub.corrected_name = name
        changed = True

    if stud_id and stud_id != sub.corrected_id:
        db.session.add(
            AuditLog(
                event_type="OCR_OVERRIDE_ID",
                user_id=current_user.id,
                test_id=sub.test_id,
                ocr_submission_id=sub.id,
                student_id=stud_id,
                original_id=sub.corrected_id,
                corrected_id=stud_id,
                description=f"Corrected ID from '{sub.corrected_id}' to '{stud_id}'"
            )
        )
        sub.corrected_id = stud_id
        changed = True

    if changed:
        sub.manual_override = True
        sub.reviewed_by = current_user.id

    return changed


# -----------------------------
# Front Page Detection
# -----------------------------
def detect_front_page(image: Image.Image) -> Image.Image:
    try:
        img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        cropped = img[y:y+h, x:x+w]
        return Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
    except Exception as e:
        current_app.logger.warning(f"[detect_front_page] Failed: {e}")
        return image


# -----------------------------
# OCR Helpers
# -----------------------------
processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
trocr_model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
trocr_model.to(device)  # type: ignore


def ocr_trocr(image: Image.Image) -> str:
    try:
        pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)  # type: ignore
        generated_ids = trocr_model.generate(pixel_values)  # type: ignore
        return processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    except Exception as e:
        current_app.logger.warning(f"[ocr_trocr] Failed: {e}")
        return ""


def ocr_tesseract(image: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(image)
    except Exception as e:
        current_app.logger.warning(f"[ocr_tesseract] Failed: {e}")
        return ""


# -----------------------------
# Fuzzy Matching
# -----------------------------
def fuzzy_match_student_id(extracted_id: str, class_list_df: "pd.DataFrame") -> Tuple[str, float]:
    choices = class_list_df['student_id'].tolist()
    match, score = process.extractOne(extracted_id, choices)
    return match, score / 100.0


# -----------------------------
# PDF Split / Organization
# -----------------------------
def split_pdf_per_student(pdf_path: Path, output_dir: Path, mapping: Dict[int, Tuple[str, str]]) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        pages = convert_from_path(str(pdf_path), dpi=300)
        for page_num, (student_id, name) in mapping.items():
            pil_image = pages[page_num]
            pdf_bytes = BytesIO()
            pil_image.save(pdf_bytes, format="PDF")
            pdf_bytes.seek(0)
            reader = PdfReader(pdf_bytes)
            writer = PdfWriter()
            writer.add_page(reader.pages[0])
            out_file = output_dir / f"{student_id}-{name}.pdf"
            with open(out_file, "wb") as f:
                writer.write(f)
    except Exception as e:
        current_app.logger.error(f"[split_pdf_per_student] Failed: {e}")


# -----------------------------
# OCR Highlighting for Debug
# -----------------------------
def highlight_keywords_in_text(text: str, keywords: List[str]) -> str:
    try:
        for kw in keywords:
            kw_escaped = re.escape(kw)
            text = re.sub(rf"({kw_escaped})", r"<mark>\1</mark>", text, flags=re.IGNORECASE)
        return text
    except Exception as e:
        current_app.logger.warning(f"[highlight_keywords_in_text] Failed: {e}")
        return text


def get_highlighted_lines_from_image(image_path: str, keywords: List[str]) -> List[str]:
    try:
        text = ocr_tesseract(Image.open(image_path))
        lines = text.splitlines()
        return [highlight_keywords_in_text(line, keywords) for line in lines]
    except Exception as e:
        current_app.logger.warning(f"[get_highlighted_lines_from_image] Failed: {e}")
        return []


# -----------------------------
# Preprocessing Pipeline
# -----------------------------
def preprocess_test_pdf(pdf_path: Path, class_list_df: "pd.DataFrame", output_dir: Path) -> Dict:
    page_mapping: Dict[int, Tuple[str, str]] = {}
    ocr_logs: List[Dict] = []

    try:
        pages = convert_from_path(str(pdf_path), dpi=300)
        for i, pil_image in enumerate(pages):
            front_img = detect_front_page(pil_image)
            text = ocr_trocr(front_img)
            if not text.strip():
                text = ocr_tesseract(front_img)

            # Placeholder extraction (replace with real OCR parsing)
            extracted_id = "ID_PLACEHOLDER"
            extracted_name = "NAME_PLACEHOLDER"

            matched_id, confidence = fuzzy_match_student_id(extracted_id, class_list_df)
            page_mapping[i] = (matched_id, extracted_name)

            ocr_logs.append({
                "page": i,
                "extracted_id": extracted_id,
                "extracted_name": extracted_name,
                "matched_id": matched_id,
                "confidence": confidence
            })

        split_pdf_per_student(pdf_path, output_dir, page_mapping)

    except Exception as e:
        current_app.logger.error(f"[preprocess_test_pdf] Failed: {e}")

    return {"page_mapping": page_mapping, "ocr_logs": ocr_logs}
