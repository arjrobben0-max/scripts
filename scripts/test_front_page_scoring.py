import os
from smartscripts.ai.ocr_engine import (
    extract_text_lines_from_image,
    score_front_page,
    is_probable_front_page,
    detect_keywords_with_positions
)


def test_folder(folder_path: str):
    """
    Iterates over image files in a folder, extracts OCR lines,
    scores front page likelihood, and highlights detected keywords.
    """
    for filename in sorted(os.listdir(folder_path)):
        if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
            continue

        image_path = os.path.join(folder_path, filename)
        print(f"\n🖼️ Processing: {filename}")

        # Extract text lines
        lines = extract_text_lines_from_image(image_path)
        text = "\n".join(lines)

        # Score front page likelihood
        score = score_front_page(text, lines)
        status = "✅ front page" if is_probable_front_page(score) else "❌ not front page"
        print(f"📈 Score: {score:.2f} ({status})")

        # Detect keywords and their positions
        matches = detect_keywords_with_positions(lines)
        for match in matches:
            print(f"🔍 Line {match['line'] + 1}: found keyword '{match['keyword']}'")


if __name__ == "__main__":
    # Update this path to the folder containing your scanned front page images
    IMAGE_FOLDER = "C:/Users/ALEX/Desktop/Smartscripts/data/scanned_images/"
    if not os.path.isdir(IMAGE_FOLDER):
        raise FileNotFoundError(f"Folder not found: {IMAGE_FOLDER}")

    test_folder(IMAGE_FOLDER)
