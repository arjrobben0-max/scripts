import os
from pathlib import Path
from typing import List, Tuple, Dict

from smartscripts.utils.pdf_helpers import convert_pdf_to_images, split_pdf_by_page_ranges
from smartscripts.ai.text_matching import load_class_list, match_ocr_pair_to_class
from smartscripts.services.analytics_service import rename_student_pdfs
from smartscripts.services.ocr_helpers import safe_extract_name_id


def ensure_dir(path: Path | str) -> None:
    """Create a directory if it doesn't exist."""
    if isinstance(path, Path):
        path.mkdir(parents=True, exist_ok=True)
    else:
        os.makedirs(path, exist_ok=True)


def main() -> None:
    test_id: int = 1
    pdf_path: Path = Path("uploads/tests/test_1/student_scripts.pdf")
    class_list_path: Path = Path("uploads/tests/test_1/class_list.csv")
    output_folder: Path = Path(f"outputs/test_{test_id}/pages")
    split_output_folder: Path = Path(f"outputs/test_{test_id}/split_pdfs")

    # Ensure output directories exist
    ensure_dir(output_folder)
    ensure_dir(split_output_folder)

    print("🔄 Converting PDF to images...")
    image_paths: List[str] = convert_pdf_to_images(
        pdf_path=str(pdf_path),
        output_dir=str(output_folder)
    )

    print("✂️ Splitting PDF into per-student scripts...")
    # Placeholder page ranges; replace with real front-page detection
    page_ranges: List[Tuple[int, int]] = [(0, len(image_paths))]
    split_paths: List[str] = split_pdf_by_page_ranges(
        pdf_path=str(pdf_path),
        page_ranges=page_ranges,
        output_dir=str(split_output_folder)
    )

    print("📋 Loading class list...")
    class_list: List[Dict[str, str]] = load_class_list(str(class_list_path))

    print("🔍 Performing OCR and matching...")
    matched_students: List[Dict[str, str]] = []
    for img_path, pdf_file in zip(image_paths, split_paths):
        # safe_extract_name_id expects a Path object
        ocr_name, ocr_id, confidence = safe_extract_name_id(Path(img_path))
        match, score = match_ocr_pair_to_class(
            ocr_name=ocr_name,
            ocr_id=ocr_id,
            class_list=class_list,
            id_weight=0.7,
            name_weight=0.3,
        )
        # Always check match before accessing keys
        if match and isinstance(match, dict):
            match["confidence"] = str(score)
            match["pdf_path"] = str(pdf_file)
            matched_students.append(match)

    print("📝 Renaming PDFs...")
    rename_student_pdfs(matched_students, upload_dir=str(split_output_folder))

    print("✅ Done!")


if __name__ == "__main__":
    main()
