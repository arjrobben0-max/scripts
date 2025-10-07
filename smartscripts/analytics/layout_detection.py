import os
import re
from pathlib import Path
import cv2
import pandas as pd
from PIL import Image
import numpy as np
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
import pytesseract
from typing import List, Tuple, Dict, Any

# ---------------------------
# 1️⃣ Load TrOCR model
# ---------------------------
processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

KEYWORDS = ["name", "id", "student", "signature", "date", "index", "admission", "reg"]

# ---------------------------
# 2️⃣ OCR Helpers
# ---------------------------
def run_trocr(image: np.ndarray) -> str:
    if image is None:
        return ""
    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    pixel_values = processor(images=pil_img, return_tensors="pt").pixel_values.to(device)
    with torch.no_grad():
        generated_ids = model.generate(pixel_values)
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return text.lower().strip()


def run_tesseract(image: np.ndarray) -> str:
    if image is None:
        return ""
    return pytesseract.image_to_string(image).lower().strip()


# ---------------------------
# 3️⃣ Layout Detection
# ---------------------------
def detect_form_lines(thresh_image: np.ndarray) -> int:
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    horizontal_lines = cv2.morphologyEx(thresh_image, cv2.MORPH_OPEN, horizontal_kernel)
    vertical_lines = cv2.morphologyEx(thresh_image, cv2.MORPH_OPEN, vertical_kernel)
    combined = cv2.add(horizontal_lines, vertical_lines)
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len(contours)


def score_front_page(image: np.ndarray) -> Tuple[float, str]:
    if image is None:
        return 0.0, ""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10
    )

    ocr_text = run_trocr(image)
    if not ocr_text.strip():
        ocr_text = run_tesseract(image)

    keyword_hits = sum(1 for word in KEYWORDS if word in ocr_text)
    keyword_score = min(keyword_hits / 4, 1.0)
    title_score = 1.0 if any(w in ocr_text for w in ["examination", "exam"]) else 0.0
    layout_score = min(detect_form_lines(thresh) / 10, 1.0)

    final_score = round(0.4 * keyword_score + 0.3 * layout_score + 0.3 * title_score, 3)
    return final_score, ocr_text


# ---------------------------
# 4️⃣ Fuzzy ID Matching
# ---------------------------
def fuzzy_match_id(ocr_text: str, class_df: pd.DataFrame) -> Tuple[Any, float]:
    if ocr_text is None:
        return None, 0.0
    ids = class_df["student_id"].astype(str).tolist()
    matches = get_close_matches(ocr_text, ids, n=1, cutoff=0.6)
    if matches:
        return matches[0], 0.9
    return None, 0.0


# ---------------------------
# 5️⃣ Main Pipeline
# ---------------------------
def detect_and_split(
    pdf_path: str,
    class_list_csv: str,
    output_dir: str = "output_scripts",
    threshold: float = 0.5
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    debug_dir = Path(output_dir) / "debug"
    debug_dir.mkdir(exist_ok=True)

    # Load class list
    class_df = pd.read_csv(class_list_csv)

    # Load PDF
    from PyPDF2 import PdfReader, PdfWriter
    pdf = PdfReader(pdf_path)
    total_pages = len(pdf.pages)

    # Pre-extracted images directory
    image_dir = Path(pdf_path).with_suffix("")
    image_paths = sorted(image_dir.glob("*.jpg"))
    if not image_paths:
        raise RuntimeError("No pre-extracted images found. Convert PDF to images first.")

    results = []
    front_page_indices = []

    for idx, image_path in enumerate(image_paths):
        image = cv2.imread(str(image_path))
        if image is None:
            continue

        score, ocr_text = score_front_page(image)
        if score >= threshold:
            front_page_indices.append(idx)

        student_id = None
        id_match = re.search(r"\b\d{4,}\b", ocr_text)
        if id_match:
            student_id = id_match.group(0)

        matched_id, conf = fuzzy_match_id(student_id or ocr_text, class_df)
        student_name = None
        if matched_id:
            row = class_df.loc[class_df["student_id"].astype(str) == str(matched_id)]
            if not row.empty:
                student_name = row.iloc[0]["name"]

        results.append({
            "page": idx + 1,
            "score": score,
            "ocr_text": ocr_text,
            "student_id": matched_id,
            "name": student_name,
            "confidence": conf,
            "matched": bool(matched_id)
        })

    # Build page ranges
    page_ranges = []
    for i, start_idx in enumerate(front_page_indices):
        start_page = start_idx
        end_page = front_page_indices[i + 1] if i + 1 < len(front_page_indices) else total_pages
        page_ranges.append((start_page, end_page))

    # Split PDFs per student
    for rng, info in zip(page_ranges, results):
        writer = PdfWriter()
        for p in range(rng[0], rng[1]):
            writer.add_page(pdf.pages[p])
        sid = info.get("student_id", "UNKNOWN")
        sname = info.get("name") or "UNMATCHED"
        filename = f"{sid}-{sname}.pdf".replace(" ", "_")
        with open(Path(output_dir) / filename, "wb") as f:
            writer.write(f)

    # Save summary table
    summary_path = Path(output_dir) / "presence_table.csv"
    pd.DataFrame(results).to_csv(summary_path, index=False)

    return {
        "results": results,
        "page_ranges": page_ranges,
        "summary_csv": str(summary_path)
    }
