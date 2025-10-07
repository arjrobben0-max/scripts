"""
smartscripts/ai/text_matching.py

Responsibilities:
- Load class list CSV
- Fuzzy match OCR-extracted name/id pairs to class list
- Produce presence table (student_id, name, matched?, confidence)
- Assign pages to students and split the original PDF into per-student PDFs (student_id-name.pdf)
- Mark uncertain pages (confidence < threshold)
- Provide keyword bounding boxes for UI highlighting
- Produce a review ZIP (PDFs + logs)
"""

import os
import csv
import io
import json
import zipfile
import logging
from typing import List, Dict, Tuple, Optional, Any
from difflib import SequenceMatcher
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Optional embedding-based similarity
_EMBED_MODEL = None
_util = None
try:
    from sentence_transformers import SentenceTransformer, util as _sentence_util  # type: ignore
    _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    _util = _sentence_util
except Exception:
    _EMBED_MODEL = None
    _util = None

# PDF utilities
PdfReader = None
PdfWriter = None
try:
    # PyPDF2 has different APIs across versions; these names should exist in modern releases
    from PyPDF2 import PdfReader, PdfWriter  # type: ignore
except Exception:
    PdfReader = None
    PdfWriter = None

# PIL / pytesseract for bounding boxes
Image = None
pytesseract = None
try:
    from PIL import Image  # type: ignore
    import pytesseract  # type: ignore
except Exception:
    Image = None
    pytesseract = None

# Try import of generate_review_zip from project (graceful fallback)
generate_review_zip = None
try:
    from smartscripts.services.ocr_utils import generate_review_zip  # type: ignore
except Exception:
    generate_review_zip = None


# ---------------------------
# Classlist loading & utils
# ---------------------------

def load_class_list(csv_path: str,
                    id_field_candidates: Optional[List[str]] = None,
                    name_field_candidates: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    Load a class list CSV and normalize to list of dicts:
    [{ "student_id": "...", "student_name": "...", ... }, ...]
    Accepts different header names by checking candidate lists.
    """
    id_field_candidates = id_field_candidates or ["student_id", "id", "reg_no", "regno", "registration_number"]
    name_field_candidates = name_field_candidates or ["student_name", "name", "full_name", "student"]

    class_list: List[Dict[str, str]] = []
    if not csv_path or not os.path.exists(csv_path):
        logger.warning("Class list CSV path missing or does not exist: %s", csv_path)
        return class_list

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        # defensively guard against missing headers
        fieldnames = reader.fieldnames or []
        headers = [h.lower() for h in fieldnames]

        id_field = None
        name_field = None
        for h in fieldnames:
            if id_field is None and h.lower() in id_field_candidates:
                id_field = h
            if name_field is None and h.lower() in name_field_candidates:
                name_field = h

        # fallback to first two columns
        if id_field is None and fieldnames:
            id_field = fieldnames[0]
        if name_field is None and len(fieldnames) > 1:
            name_field = fieldnames[1]
        elif name_field is None:
            name_field = id_field

        for row in reader:
            class_list.append({
                "student_id": (row.get(id_field) or "").strip(),
                "student_name": (row.get(name_field) or "").strip(),
                **{k: (v or "") for k, v in row.items() if k not in (id_field, name_field)}
            })

    logger.info("Loaded %d class list entries from %s", len(class_list), csv_path)
    return class_list


# ---------------------------
# Similarity helpers
# ---------------------------

def string_similarity(a: Optional[str], b: Optional[str]) -> float:
    """
    Safe string ratio in [0,1]. Returns 0.0 if either input is falsy.
    """
    if not a or not b:
        return 0.0
    try:
        return float(SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio())
    except Exception:
        return 0.0


def embedding_similarity(a: Optional[str], b: Optional[str]) -> float:
    """
    Compute embedding cosine similarity if embedding model available, otherwise fallback to string similarity.
    """
    if not a or not b:
        return 0.0
    if _EMBED_MODEL is None or _util is None:
        return string_similarity(a, b)

    try:
        # encode and compute cosine similarity
        emb = _EMBED_MODEL.encode([a, b], convert_to_tensor=True)
        sim = _util.pytorch_cos_sim(emb[0], emb[1]).item()
        return float(sim)
    except Exception as e:
        logger.debug("Embedding similarity failed, falling back to string similarity: %s", e)
        return string_similarity(a, b)


def combined_similarity(a: Optional[str], b: Optional[str], method_prefer: str = "embed") -> float:
    """
    Try embedding similarity if available, fallback to string similarity.
    Returns a score in [0,1]
    """
    if method_prefer == "embed" and _EMBED_MODEL is not None:
        s = embedding_similarity(a, b)
        # if embedding returns a meaningful score (>0) use it
        if s and s > 0:
            return s
    return string_similarity(a, b)


# ---------------------------
# Fuzzy matching logic
# ---------------------------

def fuzzy_match_id(ocr_id: Optional[str], class_list: List[Dict[str, str]], threshold: float = 0.85) -> Tuple[str, float]:
    best: Tuple[str, float] = ("", 0.0)
    if not ocr_id:
        return ("", 0.0)
    for student in class_list:
        cid = student.get("student_id", "") or ""
        score = string_similarity(ocr_id, cid)
        if score > best[1]:
            best = (cid, score)
    return best if best[1] >= threshold else ("", 0.0)


def fuzzy_match_name(ocr_name: Optional[str], class_list: List[Dict[str, str]], threshold: float = 0.8) -> Tuple[str, float]:
    best: Tuple[str, float] = ("", 0.0)
    if not ocr_name:
        return ("", 0.0)
    for student in class_list:
        cname = student.get("student_name", "") or ""
        score = combined_similarity(ocr_name, cname)
        if score > best[1]:
            best = (cname, float(score))
    return best if best[1] >= threshold else ("", 0.0)


def match_ocr_pair_to_class(ocr_id: Optional[str], ocr_name: Optional[str], class_list: List[Dict[str, str]],
                            id_weight: float = 0.7, name_weight: float = 0.3,
                            id_threshold: float = 0.80, name_threshold: float = 0.7
                            ) -> Tuple[Optional[Dict[str, str]], float]:
    """
    For a single OCR pair, return (best_student_dict or None, combined_score).
    Combined score is a weighted blend of ID and name similarity.
    """
    best_student: Optional[Dict[str, str]] = None
    best_score: float = 0.0

    for student in class_list:
        sid = student.get("student_id", "") or ""
        sname = student.get("student_name", "") or ""
        id_score = string_similarity(ocr_id or "", sid)
        name_score = combined_similarity(ocr_name or "", sname)
        combined_score = (id_weight * id_score) + (name_weight * name_score)
        if combined_score > best_score:
            best_score = combined_score
            best_student = student

    # Quick thresholding: ensure at least one of id/name passes minimal threshold
    if best_score < min(id_threshold, name_threshold):
        return None, round(best_score, 4)

    return best_student, round(best_score, 4)


# ---------------------------
# Ingest OCR results
# ---------------------------

def ingest_ocr_results(ocr_results: List[Dict[str, Any]],
                       class_list: List[Dict[str, str]],
                       id_weight: float = 0.7,
                       name_weight: float = 0.3,
                       min_match_score: float = 0.80
                       ) -> Tuple[List[Dict[str, Any]], List[Tuple[int, str, float]]]:
    """
    ocr_results: list of dicts per page containing at least:
        { "page_index": int, "text": str, "name": str, "id": str, "confidence": float }
    Returns:
      - presence_rows: list of presence table rows (one per detected OCR item)
      - assignment_rows: low-level per-page assignments (page_index -> matched_id or UNMATCHED) as list of tuples
    """
    presence_rows: List[Dict[str, Any]] = []
    assignment_rows: List[Tuple[int, str, float]] = []

    for entry in ocr_results or []:
        pid = int(entry.get("page_index") or -1)
        ocr_name = (entry.get("name") or "").strip()
        ocr_id = (entry.get("id") or "").strip()
        try:
            confidence = float(entry.get("confidence") or 0.0)
        except Exception:
            confidence = 0.0

        student, match_score = match_ocr_pair_to_class(ocr_id, ocr_name, class_list,
                                                       id_weight=id_weight, name_weight=name_weight,
                                                       id_threshold=0.6, name_threshold=0.5)

        matched = bool(student and match_score >= min_match_score)
        matched_student_id = student["student_id"] if student else ""
        matched_student_name = student["student_name"] if student else ""

        presence_rows.append({
            "page_index": pid,
            "detected_id": ocr_id,
            "detected_name": ocr_name,
            "confidence": round(confidence, 4),
            "matched": matched,
            "matched_id": matched_student_id,
            "matched_name": matched_student_name,
            "match_score": match_score
        })

        assignment_rows.append((pid, matched_student_id if matched else "UNMATCHED", match_score))

    return presence_rows, assignment_rows


# ---------------------------
# Group pages to students & split PDF
# ---------------------------

def group_pages_by_student(assignment_rows: List[Tuple[int, str, float]]) -> Dict[str, List[int]]:
    """
    Convert list of (page_index, matched_id_or_UNMATCHED, score) into mapping student_id -> [page_indices]
    UNMATCHED pages grouped under 'UNMATCHED'
    """
    mapping: Dict[str, List[int]] = defaultdict(list)
    for page_index, student_id, score in assignment_rows or []:
        mapping[student_id].append(page_index)
    return dict(mapping)


def split_pdf_to_student_pdfs(input_pdf_path: str,
                              page_mapping: Optional[Dict[str, List[int]]],
                              output_dir: str) -> List[Dict[str, Any]]:
    """
    Splits input PDF into per-student PDFs.
    Returns list of dicts: [{student_id, pages, output_path}, ...]
    Requires PyPDF2 installed.
    """
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("PyPDF2 not available. Install pyPDF2 to enable PDF splitting.")

    if not os.path.exists(input_pdf_path):
        raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")

    # ensure mapping is a dict
    page_mapping = page_mapping or {}
    os.makedirs(output_dir, exist_ok=True)

    reader = PdfReader(input_pdf_path)
    results: List[Dict[str, Any]] = []

    total_pages = len(getattr(reader, "pages", []))

    for student_id, pages in page_mapping.items():
        if student_id == "UNMATCHED":
            fname = "UNMATCHED.pdf"
        elif student_id:
            fname = f"{student_id}.pdf"
        else:
            fname = f"unknown_{len(results)+1}.pdf"

        writer = PdfWriter()
        for p in sorted(pages):
            if p < 0 or p >= total_pages:
                continue
            try:
                writer.add_page(reader.pages[p])
            except Exception:
                # compatibility fallback in case of differing PyPDF2 API
                try:
                    writer.addPage(reader.pages[p])  # older name
                except Exception:
                    logger.debug("Failed to add page %s for student %s", p, student_id)

        out_path = os.path.join(output_dir, fname)
        with open(out_path, "wb") as out_fh:
            try:
                writer.write(out_fh)
            except Exception as e:
                logger.error("Failed to write PDF %s: %s", out_path, e)
                continue

        results.append({"student_id": student_id, "pages": sorted(pages), "output_path": out_path})

    return results


def rename_student_pdfs(per_student_results: List[Dict[str, Any]],
                        mapping_student_names: Optional[Dict[str, str]],
                        output_dir: str) -> List[Dict[str, Any]]:
    """
    Rename files using student_id and student_name: student_id-student_name.pdf
    mapping_student_names: {student_id: student_name}
    """
    mapping_student_names = mapping_student_names or {}
    renamed: List[Dict[str, Any]] = []

    for info in per_student_results or []:
        sid = info.get("student_id", "")
        pages = info.get("pages", [])
        path = Path(info.get("output_path", ""))

        if sid == "UNMATCHED":
            dest = Path(output_dir) / "UNMATCHED.pdf"
        elif sid and mapping_student_names.get(sid):
            safe_name = sanitize_filename(mapping_student_names.get(sid))
            dest = Path(output_dir) / f"{sid}-{safe_name}.pdf"
        elif sid:
            dest = Path(output_dir) / f"{sid}.pdf"
        else:
            dest = Path(output_dir) / path.name

        try:
            # Use replace when possible; otherwise copy and cleanup
            path.replace(dest)
        except Exception:
            import shutil
            try:
                shutil.copy(path, dest)
                try:
                    path.unlink()
                except Exception:
                    pass
            except Exception as e:
                logger.warning("Failed to move/copy %s to %s: %s", path, dest, e)
                # still append best-effort info
                renamed.append({"student_id": sid, "pages": pages, "output_path": str(dest)})
                continue

        renamed.append({"student_id": sid, "pages": pages, "output_path": str(dest)})

    return renamed


def sanitize_filename(name: Optional[str]) -> str:
    # Accept Optional[str] and return safe filename string
    if not name:
        return "unknown"
    return "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")


# ---------------------------
# Presence table export
# ---------------------------

def export_presence_table(presence_rows: List[Dict[str, Any]], csv_path: str) -> None:
    headers = ["page_index", "detected_id", "detected_name", "confidence", "matched", "matched_id", "matched_name", "match_score"]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in presence_rows or []:
            writer.writerow({k: row.get(k, "") for k in headers})


# ---------------------------
# Uncertain pages & confidence slider helper
# ---------------------------

def mark_uncertain_pages(presence_rows: List[Dict[str, Any]], threshold: float = 0.6) -> List[Dict[str, Any]]:
    """
    Returns rows annotated with 'uncertain' flag when confidence < threshold.
    """
    for r in presence_rows or []:
        try:
            conf = float(r.get("confidence", 0.0) or 0.0)
        except Exception:
            conf = 0.0
        r["uncertain"] = (conf < threshold) or (not bool(r.get("matched", False)))
    return presence_rows


# ---------------------------
# Keyword bounding boxes for UI highlight
# ---------------------------

def detect_keyword_bboxes_from_image(image_path_or_pil: Any, keywords: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Return list of { keyword, bbox: {x,y,w,h}, text } using pytesseract image_to_data.
    image_path_or_pil may be a file path or a PIL.Image
    """
    keywords = keywords or ["name", "id", "student", "registration"]

    if pytesseract is None or Image is None:
        logger.warning("pytesseract or PIL not available; cannot compute bounding boxes.")
        return []

    try:
        if isinstance(image_path_or_pil, (str, Path)):
            img = Image.open(str(image_path_or_pil))
        else:
            img = image_path_or_pil
    except Exception as e:
        logger.warning("Failed to open image for OCR bounding boxes: %s", e)
        return []

    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:
        logger.warning("pytesseract.image_to_data failed: %s", e)
        return []

    results: List[Dict[str, Any]] = []
    text_list = data.get("text", []) or []
    lefts = data.get("left", []) or []
    tops = data.get("top", []) or []
    widths = data.get("width", []) or []
    heights = data.get("height", []) or []

    for i, txt in enumerate(text_list):
        if not txt or txt.strip() == "":
            continue
        lower = txt.strip().lower()
        for kw in keywords:
            if kw in lower:
                # guard index lookups
                try:
                    bbox = {
                        "x": int(lefts[i]) if i < len(lefts) else 0,
                        "y": int(tops[i]) if i < len(tops) else 0,
                        "w": int(widths[i]) if i < len(widths) else 0,
                        "h": int(heights[i]) if i < len(heights) else 0
                    }
                except Exception:
                    bbox = {"x": 0, "y": 0, "w": 0, "h": 0}
                results.append({
                    "keyword": kw,
                    "text": txt,
                    "bbox": bbox
                })
                break
    return results


# ---------------------------
# High-level convenience function
# ---------------------------

def preprocess_and_match_pipeline(pdf_path: str,
                                  ocr_results: List[Dict[str, Any]],
                                  class_list_csv: str,
                                  output_dir: str,
                                  confidence_threshold: float = 0.6,
                                  min_match_score: float = 0.80) -> Dict[str, Any]:
    """
    End-to-end helper used by the preprocessing task:
      - loads class list
      - matches OCR pages to students
      - groups pages and splits the PDF into per-student files
      - marks uncertain pages
      - generates presence_table.csv and a review ZIP

    Returns a dict with paths and summaries.
    """
    os.makedirs(output_dir, exist_ok=True)
    class_list = load_class_list(class_list_csv)

    presence_rows, assignment_rows = ingest_ocr_results(ocr_results, class_list,
                                                       id_weight=0.7, name_weight=0.3,
                                                       min_match_score=min_match_score)

    presence_rows = mark_uncertain_pages(presence_rows, threshold=confidence_threshold)

    # assignment_rows is already a List[Tuple[int, str, float]] from ingest_ocr_results
    page_map = group_pages_by_student(assignment_rows)

    # create per-student PDFs
    per_student = split_pdf_to_student_pdfs(pdf_path, page_map, output_dir)

    # create mapping id->name for renaming where available
    id_to_name = {s.get("student_id", ""): s.get("student_name", "") for s in class_list if s.get("student_id")}
    renamed = rename_student_pdfs(per_student, id_to_name, output_dir)

    # export presence CSV
    presence_csv_path = os.path.join(output_dir, "presence_table.csv")
    export_presence_table(presence_rows, presence_csv_path)

    # generate review zip (only if helper available)
    review_zip_path = os.path.join(output_dir, "review_bundle.zip")
    if generate_review_zip is not None:
        try:
            generate_review_zip(renamed, presence_rows, review_zip_path)
        except Exception as e:
            logger.warning("generate_review_zip failed: %s", e)
            review_zip_path = ""
    else:
        logger.warning("generate_review_zip unavailable; skipping ZIP creation.")
        review_zip_path = ""

    summary = {
        "output_dir": output_dir,
        "presence_csv": presence_csv_path,
        "review_zip": review_zip_path,
        "per_student_files": renamed,
        "presence_count": len(presence_rows)
    }
    logger.info("Preprocessing pipeline complete. Outputs in %s", output_dir)
    return summary


# Alias for backward compatibility
def fuzzy_match_name_and_id_students(extracted: List[Dict[str, Any]],
                                     class_list: List[Dict[str, str]],
                                     threshold: float = 0.85,
                                     name_weight: float = 0.5) -> List[Dict[str, Any]]:
    """
    Backward-compatible wrapper to match extracted OCR info to class list.
    Returns list of matched students (dicts with 'matched_id' and 'matched_name').
    """
    results: List[Dict[str, Any]] = []
    for ex in extracted or []:
        best_student, score = match_ocr_pair_to_class(
            ex.get("id", ""), ex.get("name", ""), class_list,
            id_weight=1.0 - name_weight, name_weight=name_weight,
            id_threshold=0.6, name_threshold=0.5
        )
        if best_student:
            results.append({
                "matched_id": best_student.get("student_id", ""),
                "matched_name": best_student.get("student_name", ""),
                "score": score
            })
    return results


def find_best_match(student_answer: str, expected_answers: List[str], threshold: float = 0.7, use_gpt_fallback: bool = False) -> Tuple[str, float]:
    """
    Returns (best_matching_answer, score)
    """
    best_score = 0.0
    best_match: str = ""
    for ans in expected_answers or []:
        try:
            score = SequenceMatcher(None, (student_answer or "").strip().lower(), ans.strip().lower()).ratio()
        except Exception:
            score = 0.0
        if score > best_score:
            best_score = score
            best_match = ans
    if best_score >= threshold:
        return best_match, best_score
    return "", best_score
