# smartscripts/utils/text_cleaner.py

import re

def clean_ocr_text(text: str) -> str:
    """
    Normalize OCR-extracted text for matching.

    Steps:
    - Convert to uppercase
    - Remove all non-alphanumeric characters
    - Strip leading/trailing whitespace
    """
    if not text:
        return ""

    # Uppercase
    text = text.upper()

    # Remove non-alphanumeric characters
    text = re.sub(r"[^A-Z0-9]", "", text)

    # Strip whitespace
    text = text.strip()

    return text


def clean_text(text: str) -> str:
    """
    Clean OCR extracted text for general processing.

    Steps:
    - Remove non-printable/control characters
    - Collapse multiple whitespace into single spaces
    - Strip leading/trailing whitespace
    - Optional: fix common OCR misreads (e.g., '0' → 'O')
    """
    if not text:
        return ""

    # Remove non-printable/control characters
    text = "".join(ch for ch in text if ch.isprintable())

    # Collapse multiple whitespace into a single space
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Optional OCR fixes:
    # text = text.replace('0', 'O').replace('1', 'I')

    return text
