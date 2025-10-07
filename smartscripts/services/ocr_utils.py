# smartscripts/services/ocr_utils.py
import os
import io
import csv
import json
import zipfile
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def generate_review_zip(
    per_student_files: List[Dict],
    presence_rows: List[Dict],
    zip_path: str,
    extra_files: Optional[List[str]] = None
) -> Path:
    """
    Create a ZIP bundle for OCR/Review workflows.

    Contents:
    - Student PDFs (from per_student_files)
    - Presence table CSV
    - Presence log JSON
    - Optional extra files

    Args:
        per_student_files: list of dicts with {"output_path": <path-to-pdf>}
        presence_rows: list of dicts containing OCR/match data
        zip_path: path where the ZIP will be written
        extra_files: optional list of additional file paths to include

    Returns:
        Path object to the created ZIP file
    """
    extra_files = extra_files or []
    zip_path_obj = Path(zip_path)
    zip_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path_obj, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Add student PDFs
        for info in per_student_files:
            out_path = info.get("output_path")
            if out_path and os.path.exists(out_path):
                zf.write(out_path, arcname=os.path.basename(out_path))

        # Generate presence CSV content
        csv_buf = io.StringIO()
        writer = csv.DictWriter(
            csv_buf,
            fieldnames=[
                "page_index", "detected_id", "detected_name", "confidence",
                "matched", "matched_id", "matched_name", "match_score", "uncertain"
            ]
        )
        writer.writeheader()
        for r in presence_rows:
            writer.writerow({k: r.get(k, "") for k in writer.fieldnames})
        zf.writestr("presence_table.csv", csv_buf.getvalue())

        # Add JSON log
        zf.writestr("presence_log.json", json.dumps(presence_rows, indent=2, ensure_ascii=False))

        # Add extra files
        for f in extra_files:
            if os.path.exists(f):
                zf.write(f, arcname=os.path.basename(f))

    logger.info(f"Review ZIP created at {zip_path_obj}")
    return zip_path_obj
