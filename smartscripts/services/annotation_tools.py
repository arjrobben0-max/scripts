import os
from typing import List, Optional
from io import BytesIO

import numpy as np
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image, ImageDraw, ImageFont

from smartscripts.utils.file_io import ensure_folder_exists


# -----------------------------
# PDF Report Utilities
# -----------------------------

def create_pdf_report(
    output_path: str, title: str = "Report", content: str = ""
) -> str:
    ensure_folder_exists(os.path.dirname(output_path))
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2.0, height - 72, title)

    c.setFont("Helvetica", 12)
    text_object = c.beginText(72, height - 108)
    for line in content.split("\n"):
        text_object.textLine(line)
    c.drawText(text_object)

    c.showPage()
    c.save()

    return output_path


def annotate_pdf_with_text(
    input_pdf_path: str,
    output_pdf_path: str,
    annotations: List[dict],
):
    ensure_folder_exists(os.path.dirname(output_pdf_path))

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        for ann in annotations:
            if ann["page"] == i:
                font_size = ann.get("font_size", 12)
                can.setFont("Helvetica", font_size)
                can.setFillColorRGB(1, 0, 0)
                can.drawString(ann["x"], ann["y"], ann["text"])
        can.save()
        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)


# -----------------------------
# Image Annotation Utilities
# -----------------------------
# NOTE: The previous code relied on missing functions.
# We can keep a stub version or refactor to use generate_overlay_pdf.

def annotate_image_with_text(
    input_image_path: str,
    output_image_path: str,
    annotations: List[dict],
    keywords: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    threshold: float = 0.7,
):
    """
    Basic image annotation (without add_overlay / highlight_keywords / annotate_confidence).
    """
    ensure_folder_exists(os.path.dirname(output_image_path))

    img = Image.open(input_image_path).convert("RGBA")
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    font_size_default = 20
    try:
        font_default = ImageFont.truetype("arial.ttf", font_size_default)
    except IOError:
        font_default = ImageFont.load_default()

    for ann in annotations:
        fs = ann.get("font_size", font_size_default)
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except IOError:
            font = font_default
        color = ann.get("color", (255, 0, 0))
        draw.text((ann["x"], ann["y"]), ann["text"], fill=color + (255,), font=font)

    combined = Image.alpha_composite(img, txt_layer)
    combined.convert("RGB").save(output_image_path)


# -----------------------------
# Per-Student PDF Handling
# -----------------------------

def split_and_annotate_student_pdf(
    input_pdf_path: str,
    output_dir: str,
    student_page_ranges: dict,
    annotations_per_student: Optional[dict] = None,
    keywords_per_student: Optional[dict] = None,
    confidence_per_student: Optional[dict] = None,
) -> dict:
    ensure_folder_exists(output_dir)
    reader = PdfReader(input_pdf_path)
    output_paths = {}

    for student_id, ranges in student_page_ranges.items():
        writer = PdfWriter()
        for start, end in ranges:
            for i in range(start, end + 1):
                writer.add_page(reader.pages[i])

        student_pdf_path = os.path.join(output_dir, f"{student_id}.pdf")
        with open(student_pdf_path, "wb") as f_out:
            writer.write(f_out)

        # Annotations: call your image annotation (stub)
        annotations = annotations_per_student.get(student_id, []) if annotations_per_student else []

        if annotations:
            for idx in range(len(ranges)):
                img_path = student_pdf_path  # Simplification: in real code convert PDF page to image
                out_img_path = os.path.join(output_dir, f"{student_id}_page_{idx}.png")
                annotate_image_with_text(img_path, out_img_path, annotations)

        output_paths[student_id] = student_pdf_path

    return output_paths
