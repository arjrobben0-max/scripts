# smartscripts/utils/image_helpers.py

from pathlib import Path
from typing import List, Union
from PIL import Image
import uuid
from flask import current_app
import cv2
import numpy as np

# Import add_overlay from new utility module
from smartscripts.utils.overlay_utils import add_overlay

# -------------------------------
# OCR Keyword & Confidence Utilities
# -------------------------------

def highlight_keywords(image: np.ndarray, keywords: List[str]) -> np.ndarray:
    """
    Draw bounding boxes or highlights for OCR keywords.
    Placeholder: Actual bounding boxes should come from OCR result.
    """
    for kw in keywords:
        # Example: cv2.rectangle(image, (x1, y1), (x2, y2), color=(0,255,0), thickness=2)
        pass
    return image


def annotate_confidence(image: np.ndarray, confidence: float, threshold: float = 0.7) -> np.ndarray:
    """
    Mark low-confidence pages with a cross overlay.
    """
    if confidence < threshold:
        image = add_overlay(image, "cross", position=(10, 10), scale=0.15)
    return image

# -------------------------------
# Dynamic Image Saving / Merging
# -------------------------------

def merge_images_vertically(image_paths: List[str], subfolder: str = "images") -> str:
    images = [Image.open(p) for p in image_paths]
    widths, heights = zip(*(img.size for img in images))
    merged_image = Image.new("RGB", (max(widths), sum(heights)), color=(255, 255, 255))
    y_offset = 0
    for img in images:
        merged_image.paste(img, (0, y_offset))
        y_offset += img.height

    static_dir = Path(current_app.root_path) / "static" / subfolder
    static_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}.png"
    output_path = static_dir / filename
    merged_image.save(output_path, format="PNG")
    return f"{subfolder}/{filename}"


def save_dynamic_image(img: Image.Image, subfolder: str = "images") -> str:
    static_dir = Path(current_app.root_path) / "static" / subfolder
    static_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}.png"
    output_path = static_dir / filename
    img.save(output_path, format="PNG")
    return f"{subfolder}/{filename}"

# -------------------------------
# Save list of images as PDF
# -------------------------------

def save_images_as_pdf(images: List[np.ndarray], pdf_path: Union[str, Path]) -> None:
    """
    Save a list of numpy images (BGR or RGB) into a single PDF.
    """
    pdf_path = Path(pdf_path)
    pil_images = []

    for img in images:
        if img.ndim == 3 and img.shape[2] == 3:
            # Convert BGR (OpenCV default) → RGB for Pillow
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img
        pil_images.append(Image.fromarray(img_rgb))

    if pil_images:
        pil_images[0].save(
            pdf_path,
            save_all=True,
            append_images=pil_images[1:],
            format="PDF",
            resolution=200,
        )

# -------------------------------
# Overlay / Drawing Utilities
# -------------------------------

def draw_marks_on_script(image: np.ndarray, marks: list) -> np.ndarray:
    for mark in marks:
        x, y, w, h = mark.get("x", 0), mark.get("y", 0), mark.get("w", 0), mark.get("h", 0)
        color = mark.get("color", (255, 0, 0))
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
    return image


def save_overlay_image(image: Union[np.ndarray, Image.Image], output_path: Union[str, Path]) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(image, np.ndarray):
        img_to_save = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image
        Image.fromarray(img_to_save).save(output_path)
    else:
        image.save(output_path)
