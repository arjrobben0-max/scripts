# smartscripts/utils/file_ops.py

import os
import csv
import shutil
from datetime import datetime
from typing import List, Tuple
from PyPDF2 import PdfReader, PdfWriter
from flask import current_app


# -------------------------------
# PDF Utilities
# -------------------------------

def split_pdf_by_page_ranges(
    pdf_path: str, page_ranges: List[Tuple[int, int]], output_dir: str
) -> List[str]:
    """
    Split PDF into multiple files based on page ranges.

    Args:
        pdf_path (str): Path to the input PDF.
        page_ranges (List[Tuple[int,int]]): List of (start_page, end_page) tuples (0-indexed).
        output_dir (str): Directory to save split PDFs.

    Returns:
        List[str]: Paths of the split PDF files.
    """
    os.makedirs(output_dir, exist_ok=True)
    reader = PdfReader(pdf_path)
    output_paths = []

    for idx, (start, end) in enumerate(page_ranges):
        writer = PdfWriter()
        for i in range(start, end + 1):
            if i < len(reader.pages):
                writer.add_page(reader.pages[i])
            else:
                current_app.logger.warning(f"Page {i} out of bounds for {pdf_path}")

        out_path = os.path.join(output_dir, f"part_{idx + 1}.pdf")
        with open(out_path, "wb") as f_out:
            writer.write(f_out)
        output_paths.append(out_path)
        current_app.logger.info(f"Created split PDF: {out_path}")

    return output_paths


# -------------------------------
# Manifest Utilities
# -------------------------------

def duplicate_manifest_for_reference(test_id: int, upload_root: str) -> str:
    """
    Copy manifest.csv from manifests folder to submissions folder for reference.
    """
    src = os.path.join(upload_root, "manifests", str(test_id), "manifest.csv")
    dest_dir = os.path.join(upload_root, "submissions", str(test_id))
    dest = os.path.join(dest_dir, "manifest.csv")

    if not os.path.exists(src):
        raise FileNotFoundError(f"Manifest not found at: {src}")

    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(src, dest)
    current_app.logger.info(f"📄 Manifest duplicated to: {dest}")
    return dest


def update_manifest(test_id: int, student_id: str, pages_uploaded: int, upload_root: str) -> str:
    """
    Update the manifest.csv for a test to log pages uploaded for a student.
    Creates manifest if it does not exist.
    """
    manifest_dir = os.path.join(upload_root, "manifests", str(test_id))
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "manifest.csv")

    rows = []
    found = False

    if os.path.exists(manifest_path):
        with open(manifest_path, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row["student_id"] == str(student_id):
                    row["pages_uploaded"] = str(pages_uploaded)
                    row["timestamp"] = datetime.utcnow().isoformat()
                    found = True
                rows.append(row)

    if not found:
        rows.append({
            "student_id": str(student_id),
            "pages_uploaded": str(pages_uploaded),
            "timestamp": datetime.utcnow().isoformat(),
        })

    with open(manifest_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["student_id", "pages_uploaded", "timestamp"])
        writer.writeheader()
        writer.writerows(rows)

    current_app.logger.info(f"✅ Manifest updated: {manifest_path}")
    return manifest_path
