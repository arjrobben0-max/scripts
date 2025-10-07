import os
import re
import io
import base64
import multiprocessing
from pathlib import Path
from typing import List, Tuple, Optional, Union

import torch
from PIL import Image, ImageOps, ImageChops
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from pdf2image import convert_from_path

# === Tesseract ===
try:
    import pytesseract
except ImportError:
    pytesseract = None
    print("⚠️ pytesseract not installed. Tesseract fallback will be disabled.")

# === OpenAI (Optional) ===
try:
    import openai
except ImportError:
    openai = None
    print("⚠️ OpenAI not installed. GPT-based features will be disabled.")

# === Device & Model Setup ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten").to(device)
model.eval()

# === Constants ===
KEYWORDS = [
    "name", "student name", "full name",
    "id", "student id", "reg no", "registration number"
]

# =====================================================
# =============== OCR MAIN FUNCTIONS ==================
# =====================================================

def run_ocr_on_test(pdf_path: str) -> dict:
    images = convert_from_path(str(pdf_path), dpi=300)
    if not images:
        return {"name": "", "id": "", "confidence": 0.0, "matched": None}

    first_page_img = images[0]
    with io.BytesIO() as buf:
        first_page_img.save(buf, format="PNG")
        buf.seek(0)
        text = extract_text_from_image(buf)

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    name, student_id = "", ""
    for line in lines:
        if not student_id and re.match(r"^[A-Za-z0-9\-/\s]{5,20}$", line):
            student_id = line
        elif not name and re.match(r"^[A-Z][A-Za-z\-]+(?:\s[A-Z][A-Za-z\-]+){0,3}$", line, re.IGNORECASE):
            name = line
        if name and student_id:
            break

    confidence = estimate_ocr_confidence(text)
    return {"name": name, "id": student_id, "confidence": confidence, "matched": None}


def extract_text_from_pdf(pdf_path: str, output_text_path: Optional[str] = None) -> str:
    images = convert_from_path(str(pdf_path), dpi=300)
    with multiprocessing.Pool() as pool:
        results = pool.starmap(_ocr_page, [(i, img) for i, img in enumerate(images)])

    joined_text = "\n\n".join(results)
    if output_text_path:
        with open(output_text_path, "w", encoding="utf-8") as f:
            f.write(joined_text)
    return joined_text


def extract_text_from_image(
    image_input: Union[str, Path, io.BytesIO],
    confidence_threshold: float = 0.7,
    do_fallback: bool = True,
    do_refine: bool = True
) -> str:
    if isinstance(image_input, (str, Path)):
        image = Image.open(str(image_input))
    else:
        image = Image.open(image_input)

    trocr_text, confidence = trocr_extract_with_confidence(image)
    final_text = trocr_text

    if do_fallback and (not trocr_text or confidence < confidence_threshold) and pytesseract:
        tess_text = pytesseract.image_to_string(image)
        if tess_text.strip():
            final_text = tess_text.strip()

    if do_fallback and (not final_text or len(final_text) < 5):
        vision_text = gpt4_vision_extract(image)
        if vision_text:
            final_text = vision_text

    if do_refine and final_text:
        final_text = gpt4_chat_refine(final_text)

    return final_text

# =====================================================
# =============== OCR HELPER FUNCTIONS ================
# =====================================================

def preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    bg = Image.new(image.mode, image.size, image.getpixel((0, 0)))
    diff = ImageChops.difference(image, bg)
    bbox = diff.getbbox()
    return image.crop(bbox) if bbox else image

def estimate_ocr_confidence(text: str) -> float:
    if not text.strip():
        return 0.0
    confidence = 1.0
    if re.search(r"[#@~%^*]{2,}", text):
        confidence -= 0.3
    if len(text.strip()) < 5:
        confidence -= 0.2
    return max(confidence, 0.0)

def run_tr_ocr(image: Image.Image) -> str:
    pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)
    with torch.no_grad():
        generated_ids = model.generate(pixel_values)
        predicted_texts = processor.batch_decode(generated_ids, skip_special_tokens=True)
    return predicted_texts[0].strip() if predicted_texts else ""

def trocr_extract_with_confidence(image: Image.Image) -> Tuple[str, float]:
    processed = preprocess_image(image)
    text = run_tr_ocr(processed)
    confidence = estimate_ocr_confidence(text)
    return text, confidence

# =====================================================
# =============== GPT-4 INTEGRATION ==================
# =====================================================

def gpt4_vision_extract(image: Image.Image) -> str:
    if not openai or not os.getenv("OPENAI_API_KEY"):
        return ""
    openai.api_key = os.getenv("OPENAI_API_KEY")
    try:
        with io.BytesIO() as buf:
            image.save(buf, format="PNG")
            encoded_image = base64.b64encode(buf.getvalue()).decode("utf-8")
        response = openai.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {"role": "user", "content": "Extract all readable handwritten text from this exam page."},
                {"role": "user", "content": f"data:image/png;base64,{encoded_image}"}
            ],
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GPT-4 Vision Error] {e}")
        return ""

def gpt4_chat_refine(text: str) -> str:
    if not openai or not os.getenv("OPENAI_API_KEY") or not text:
        return text
    openai.api_key = os.getenv("OPENAI_API_KEY")
    try:
        prompt = (
            "The following text was extracted from a handwritten exam paper. "
            "Please correct any OCR or formatting errors:\n\n"
            f"{text}\n\nCleaned text:"
        )
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GPT-4 Chat Error] {e}")
        return text

# =====================================================
# =============== EXTRA UTILITIES =====================
# =====================================================

def _ocr_page(index: int, image: Image.Image) -> str:
    with io.BytesIO() as buf:
        image.save(buf, format="PNG")
        buf.seek(0)
        page_text = extract_text_from_image(buf)
    return f"--- Page {index + 1} ---\n{page_text}"

def extract_text_lines_from_image(image_path: str) -> List[str]:
    text = extract_text_from_image(image_path)
    return [line.strip() for line in text.split("\n") if line.strip()]

def score_front_page(text: str, lines: List[str]) -> float:
    matched_keywords = 0
    top_hits = 0
    for i, line in enumerate(lines[:10]):
        for keyword in KEYWORDS:
            if re.search(rf"\b{keyword}\b", line.lower()):
                matched_keywords += 1
                if i < 5:
                    top_hits += 1
    if matched_keywords == 0:
        return 0.0
    weighted_score = matched_keywords + 0.5 * top_hits
    normalized_score = min(weighted_score / (len(KEYWORDS) + 5), 1.0)
    return round(normalized_score, 3)

def is_probable_front_page(score: float, threshold: float = 0.6) -> bool:
    return score >= threshold

def detect_keywords_with_positions(
    lines: List[str], image: Optional[Image.Image] = None
) -> List[dict]:
    matches = []
    for i, line in enumerate(lines):
        for keyword in KEYWORDS:
            if re.search(rf"\b{keyword}\b", line.lower()):
                entry = {"line": i, "keyword": keyword}
                if image and pytesseract:
                    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                    for j, word in enumerate(data["text"]):
                        if keyword in word.lower():
                            entry["bbox"] = {
                                "x": data["left"][j],
                                "y": data["top"][j],
                                "w": data["width"][j],
                                "h": data["height"][j]
                            }
                            break
                matches.append(entry)
    return matches

def extract_name_id_from_image(image_path: str) -> Tuple[str, str]:
    full_text = extract_text_from_image(image_path)
    lines = [line.strip() for line in full_text.split("\n") if line.strip()]

    name, student_id = "", ""
    for line in lines:
        if not student_id and re.match(r"^[A-Za-z0-9\-/\s]{5,20}$", line):
            student_id = line
        elif not name and re.match(r"^[A-Z][A-Za-z\-]+(?:\s[A-Z][A-Za-z\-]+){0,3}$", line, re.IGNORECASE):
            name = line
        if name and student_id:
            break

    return name, student_id
