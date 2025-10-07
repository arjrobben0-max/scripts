from pathlib import Path
import logging
from typing import List, Tuple, Dict
from collections import defaultdict
from werkzeug.utils import secure_filename

from smartscripts.utils.pdf_helpers import (
    convert_pdf_to_images,
    split_pdf_by_page_ranges,
    is_front_page,
)
from smartscripts.ai.ocr_engine import extract_name_id_from_image

logger = logging.getLogger(__name__)


# -----------------------------
# 1️⃣ PDF → Images
# -----------------------------
def pdf_to_images(pdf_path: Path) -> List[Path]:
    """Convert a PDF into images stored in a temporary folder."""
    tmp_dir = pdf_path.parent / "tmp_images"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    images, _ = convert_pdf_to_images(str(pdf_path), output_dir=str(tmp_dir))
    logger.info("Converted %s to %d images", pdf_path.name, len(images))
    return [Path(img) for img in images]


# -----------------------------
# 2️⃣ OCR Helpers
# -----------------------------
def run_trocr(image_path: Path) -> Tuple[str, str, float]:
    """Run TrOCR on an image to extract Name & ID."""
    try:
        result = extract_name_id_from_image(str(image_path))
        if result and len(result) == 3:
            return result
    except Exception as e:
        logger.warning("TrOCR failed on %s: %s", image_path, e)
    return "Unknown", "Unknown", 0.0


def run_tesseract_fallback(image_path: Path) -> Tuple[str, str, float]:
    """Run Tesseract OCR as a fallback for Name & ID extraction."""
    try:
        result = extract_name_id_from_image(str(image_path))
        if result and len(result) == 3:
            return result
    except Exception as e:
        logger.warning("Tesseract failed on %s: %s", image_path, e)
    return "Unknown", "Unknown", 0.0


def safe_extract_name_id(image_path_or_obj: Path) -> Tuple[str, str, float]:
    """Safely extract Name & ID from an image or object. Always returns a 3-tuple."""
    result = run_trocr(image_path_or_obj)
    if not result or len(result) != 3:
        result = run_tesseract_fallback(image_path_or_obj)
    name, student_id, confidence = result
    return name or "Unknown", student_id or "Unknown", confidence or 0.0


# -----------------------------
# 3️⃣ Front Page Detection
# -----------------------------
def detect_student_front_pages(images: List[Path]) -> List[Tuple[int, int]]:
    """Detect ranges of pages belonging to each student based on front pages."""
    page_ranges = []
    start_idx = None
    for i, img in enumerate(images):
        if is_front_page(str(img)):
            if start_idx is not None:
                page_ranges.append((start_idx, i - 1))
            start_idx = i
    if start_idx is not None:
        page_ranges.append((start_idx, len(images) - 1))
    logger.info("Detected %d student page ranges", len(page_ranges))
    return page_ranges


# -----------------------------
# 4️⃣ Split PDF Per Student
# -----------------------------
def split_pdf_for_student(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    student_name: str,
    student_id: str,
    output_dir: Path
) -> Path:
    """
    Split the main PDF into a single student script PDF.
    Returns the path of the created student PDF.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Split PDF by page ranges
    split_paths = split_pdf_by_page_ranges(
        str(pdf_path),
        ranges=[(start_page, end_page)],
        output_dir=str(output_dir)
    )
    if not split_paths:
        raise RuntimeError(f"Failed to split PDF for {student_id}-{student_name}")

    output_path = Path(split_paths[0])

    # Optionally rename to safe student ID + name
    safe_name = secure_filename(student_name or "unknown")
    safe_id = secure_filename(student_id or "unknown")
    renamed_path = output_dir / f"{safe_id}-{safe_name}.pdf"
    output_path.rename(renamed_path)

    return renamed_path


def rename_student_pdfs(
    student_pdfs: List[Path],
    student_map: Dict[int, Tuple[str, str]],
    output_dir: Path
) -> List[Path]:
    """
    Rename per-student PDFs using student_map.
    Ensures safe filenames and returns list of renamed Paths.
    """
    renamed_pdfs: List[Path] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for pdf_path in student_pdfs:
        # Extract ID and name from student_map or filename
        original_name = pdf_path.stem
        sid, name = "unknown", "unknown"
        for (page, (student_id, student_name)) in student_map.items():
            if student_name in original_name or student_id in original_name:
                sid, name = student_id, student_name
                break

        safe_name = secure_filename(name)
        safe_sid = secure_filename(sid)
        renamed_filename = output_dir / f"{safe_sid}-{safe_name}.pdf"
        pdf_path.rename(renamed_filename)
        renamed_pdfs.append(renamed_filename)

    return renamed_pdfs


# -----------------------------
# 5️⃣ Text Normalization
# -----------------------------
def normalize_text(text: str) -> str:
    """Normalize OCR text: lowercase, remove extra spaces and linebreaks."""
    return " ".join(text.strip().lower().split())


# -----------------------------
# 6️⃣ Confidence / UI Hooks
# -----------------------------
def mark_uncertain(script_data: dict, threshold: float = 0.8) -> dict:
    """Mark scripts with OCR confidence below threshold."""
    confidence = script_data.get("ocr_confidence", 0.0) or 0.0
    script_data["is_uncertain"] = confidence < threshold
    return script_data
