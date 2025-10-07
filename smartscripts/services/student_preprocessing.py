# File: smartscripts/services/student_preprocessing.py

from pathlib import Path
from typing import List, Dict, Any, Optional
from smartscripts.utils.file_helpers import get_extracted_dir
from smartscripts.models import StudentSubmission as Submission
import logging

logger = logging.getLogger(__name__)


def preprocess_student_submissions(
    combined_pdf_path: Path,
    test_id: int,
    class_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Preprocess student submissions for a test.
    
    Steps:
    1. Split the combined PDF into per-student PDFs.
    2. Detect student IDs/names from each page.
    3. Match detected students against class_list (if provided).
    4. Return a dictionary containing extracted student scripts info.

    Args:
        combined_pdf_path (Path): Path to the combined PDF of all student submissions.
        test_id (int): The test/exam identifier.
        class_list (Optional[List[Dict[str, Any]]]): Optional list of student info for matching.

    Returns:
        Dict[str, Any]: Dictionary with key 'extracted_student_script' containing list of extracted submissions.
    """
    if class_list is None:
        class_list = []

    # Directory where extracted per-student PDFs will be stored
    extracted_dir = get_extracted_dir(test_id)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    # Placeholder: implement real OCR, splitting, and detection here
    extracted_student_script: List[Submission] = []

    # Example dummy implementation:
    # - In a real implementation, you would split the PDF
    # - Run OCR on each page
    # - Extract student ID and name
    # - Create Submission instances
    # For now, we just return an empty list

    logger.info(
        f"Preprocessing done for test {test_id}, extracted {len(extracted_student_script)} student scripts"
    )

    return {"extracted_student_script": extracted_student_script}
