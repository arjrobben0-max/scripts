# smartscripts/utils/export_helpers.py

import os
import zipfile
from pathlib import Path
from typing import List, Dict
from fpdf import FPDF
from flask import current_app
from .csv_helpers import read_class_list


def export_marks_to_pdf(student_data: List[Dict], output_path: str) -> str:
    """
    Generate a final marksheet PDF from student scores.

    Args:
        student_data (List[Dict]): List of dicts with keys 'id', 'name', 'score'.
        output_path (str): Path to save the generated PDF.

    Returns:
        str: Path to the generated PDF.
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Final Marksheet", ln=1, align='C')

        for student in student_data:
            line = f"{student.get('id', '')} - {student.get('name', '')} - {student.get('score', '')}"
            pdf.cell(200, 10, txt=line, ln=1, align='L')

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pdf.output(output_path)
        current_app.logger.info(f"Generated marksheet PDF at {output_path}")
        return output_path
    except Exception as e:
        current_app.logger.error(f"Failed to generate marksheet PDF: {e}")
        raise


def zip_student_outputs(student_pdfs: List[str], attendance_csv: str, output_zip: str) -> str:
    """
    Create a ZIP file containing all student PDFs and attendance CSV.

    Args:
        student_pdfs (List[str]): List of student PDF file paths.
        attendance_csv (str): Path to attendance CSV file.
        output_zip (str): Path to save the ZIP file.

    Returns:
        str: Path to the generated ZIP file.
    """
    try:
        os.makedirs(os.path.dirname(output_zip), exist_ok=True)
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for pdf_path in student_pdfs:
                if Path(pdf_path).exists():
                    zipf.write(pdf_path, Path(pdf_path).name)
            if Path(attendance_csv).exists():
                zipf.write(attendance_csv, "attendance.csv")

        current_app.logger.info(f"Created ZIP file at {output_zip}")
        return output_zip
    except Exception as e:
        current_app.logger.error(f"Failed to create ZIP file: {e}")
        raise


def export_attendance(class_list_file: str, matched_students: List[Dict], unmatched_students: List[Dict], output_csv: str) -> str:
    """
    Export attendance CSV marking matched and unmatched students.

    Args:
        class_list_file (str): Path to the original class list CSV.
        matched_students (List[Dict]): Students successfully matched via OCR.
        unmatched_students (List[Dict]): Students not matched.
        output_csv (str): Output path for attendance CSV.

    Returns:
        str: Path to the generated CSV.
    """
    try:
        class_list = read_class_list(Path(class_list_file))
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)

        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            import csv
            writer = csv.writer(f)
            writer.writerow(["Student ID", "Name", "Status"])
            for student in class_list:
                status = "Matched" if student in matched_students else "Unmatched"
                writer.writerow([student.get("student_id", ""), student.get("name", ""), status])

        current_app.logger.info(f"Exported attendance CSV at {output_csv}")
        return output_csv
    except Exception as e:
        current_app.logger.error(f"Failed to export attendance CSV: {e}")
        raise
