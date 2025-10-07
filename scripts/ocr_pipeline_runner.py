import logging
from pathlib import Path
from celery import shared_task

from smartscripts.ai.ocr_engine import extract_name_id_from_image
from smartscripts.utils import pdf_helpers  # Ensure convert_pdf_to_images exists

# Configure logging
logging.basicConfig(
    filename="logs/ocr_pipeline.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


@shared_task(bind=True)
def run_ocr_on_test(self, test_id: int, student_id: str):
    logging.info(f"Starting OCR pipeline for test: {test_id}, student: {student_id}")

    # Paths
    root_dir = Path("uploads/submissions")
    submission_dir = root_dir / str(test_id) / str(student_id)
    output_dir = submission_dir

    # Check submission folder
    if not submission_dir.exists():
        error_msg = f"Submission directory not found: {submission_dir}"
        logging.error(error_msg)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        return {'status': 'failed', 'reason': error_msg}

    pdf_path = submission_dir / "original.pdf"
    if not pdf_path.exists():
        error_msg = f"PDF not found: {pdf_path}"
        logging.error(error_msg)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        return {'status': 'failed', 'reason': error_msg}

    # Step 1: Convert PDF to images
    try:
        # convert_pdf_to_images should return a list of image paths and optionally page ranges
        image_paths, page_ranges = pdf_helpers.convert_pdf_to_images(
            pdf_path=str(pdf_path),
            output_dir=str(output_dir)
        )
        logging.info(f"Converted PDF to {len(image_paths)} images")
        logging.info(f"Page ranges: {page_ranges}")
    except Exception as e:
        logging.error(f"PDF to image conversion failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {'status': 'failed', 'reason': str(e)}

    # Step 2: Run OCR on each image
    total_pages = len(image_paths)
    ocr_results = []
    for idx, image_path in enumerate(image_paths, start=1):
        try:
            name, student_id_extracted, confidence = extract_name_id_from_image(str(image_path))
            ocr_results.append({
                "image": str(image_path),
                "name": name,
                "student_id": student_id_extracted,
                "confidence": confidence
            })
            logging.info(f"OCR completed for page {idx}/{total_pages}: {name}, {student_id_extracted}")

            # Save OCR text to file (optional)
            ocr_text_path = output_dir / f"page_{idx}.txt"
            ocr_text_path.write_text(f"Name: {name}\nID: {student_id_extracted}\nConfidence: {confidence}", encoding="utf-8")

            # Update Celery task progress
            self.update_state(state='PROGRESS', meta={
                'current': idx,
                'total': total_pages,
                'progress': int((idx / total_pages) * 100)
            })

        except Exception as e:
            logging.error(f"OCR failed for {image_path.name}: {e}")
            continue  # Skip failed pages

    logging.info(f"OCR pipeline completed successfully for {submission_dir.name}")
    return {
        'status': 'success',
        'message': 'OCR completed',
        'ocr_results': ocr_results,
        'page_ranges': page_ranges
    }
