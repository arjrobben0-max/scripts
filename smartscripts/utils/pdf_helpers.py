# smartscripts/utils/pdf_helpers.py

from pathlib import Path
from typing import List, Union, Tuple
from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter
import numpy as np
from PIL import Image
import cv2

# -------------------------------
# PDF → Images
# -------------------------------

def convert_pdf_to_images(pdf_path: Union[str, Path], dpi: int = 200) -> List[np.ndarray]:
    pdf_path = Path(pdf_path)
    pages = convert_from_path(str(pdf_path), dpi=dpi)
    return [np.array(page.convert("RGB")) for page in pages]

# -------------------------------
# Single Page → PNG/JPG
# -------------------------------

def save_pdf_page_as_image(
    pdf_path: Union[str, Path],
    page_number: int,
    output_path: Union[str, Path],
    dpi: int = 200,
    image_format: str = "PNG",
) -> Path:
    pages = convert_from_path(str(pdf_path), dpi=dpi, first_page=page_number + 1, last_page=page_number + 1)
    if not pages:
        raise ValueError(f"Page {page_number} not found in {pdf_path}")
    page_image: Image.Image = pages[0].convert("RGB")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_image.save(output_path, format=image_format.upper())
    return output_path

# -------------------------------
# Extract First Page Thumbnail
# -------------------------------

def get_pdf_thumbnail(pdf_path: Union[str, Path], dpi: int = 100) -> np.ndarray:
    pages = convert_from_path(str(pdf_path), dpi=dpi, first_page=1, last_page=1)
    if not pages:
        raise ValueError(f"No pages found in {pdf_path}")
    return np.array(pages[0].convert("RGB"))

# -------------------------------
# Split PDF by Page Ranges
# -------------------------------

def split_pdf_by_page_ranges(
    pdf_path: Union[str, Path],
    output_dir: Union[str, Path],
    ranges: List[Tuple[int, int]]
) -> List[Path]:
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    output_paths = []

    for i, (start, end) in enumerate(ranges, start=1):
        writer = PdfWriter()
        for page_num in range(start - 1, end):
            if page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])
        split_path = output_dir / f"{pdf_path.stem}_part{i}.pdf"
        with open(split_path, "wb") as f:
            writer.write(f)
        output_paths.append(split_path)

    return output_paths

# -------------------------------
# Save numpy images as PDF
# -------------------------------

def save_images_as_pdf(images: List[np.ndarray], pdf_path: Union[str, Path]) -> None:
    pil_images = []
    for img in images:
        if img.ndim == 3 and img.shape[2] == 3:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img
        pil_images.append(Image.fromarray(img_rgb))
    if pil_images:
        Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)
        pil_images[0].save(
            Path(pdf_path),
            save_all=True,
            append_images=pil_images[1:],
            resolution=200,
        )

# -------------------------------
# Check if PDF is front page
# -------------------------------

def is_front_page(pdf_path: Union[str, Path]) -> bool:
    """
    Return True if PDF has only one page.
    """
    pdf_path = Path(pdf_path)
    reader = PdfReader(str(pdf_path))
    return len(reader.pages) == 1
