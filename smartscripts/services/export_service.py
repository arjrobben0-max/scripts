import io
import os
import csv
import zipfile
from typing import List, Dict, Optional, Union, Any
from fpdf import FPDF


class ExportService:
    """
    Service for exporting student submissions to CSV, PDF, and ZIP with feedback artifacts.
    """

    @staticmethod
    def export_submissions_to_csv(
        submissions: List[Union[Dict[str, Any], object]],
        fieldnames: Optional[List[str]] = None,
    ) -> str:
        if not submissions:
            raise ValueError("No submissions data provided for CSV export")

        # Ensure all entries are dicts
        data: List[Dict[str, Any]] = []
        for sub in submissions:
            if isinstance(sub, dict):
                data.append(sub)
            elif hasattr(sub, "to_dict") and callable(getattr(sub, "to_dict")):
                data.append(sub.to_dict())
            else:
                raise ValueError("Submission must be a dict or have a to_dict() method")

        output = io.StringIO()
        if fieldnames is None:
            fieldnames = list(data[0].keys())

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_submissions_to_pdf(
        submissions: List[Union[Dict[str, Any], object]], title: str = "Submissions Report"
    ) -> bytes:
        if not submissions:
            raise ValueError("No submissions data provided for PDF export")

        data: List[Dict[str, Any]] = []
        for sub in submissions:
            if isinstance(sub, dict):
                data.append(sub)
            elif hasattr(sub, "to_dict") and callable(getattr(sub, "to_dict")):
                data.append(sub.to_dict())
            else:
                raise ValueError("Submission must be a dict or have a to_dict() method")

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()

        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, title, ln=True, align="C")
        pdf.ln(8)

        pdf.set_font("Arial", size=11)
        keys = list(data[0].keys())
        page_width = pdf.w - 2 * pdf.l_margin
        col_width = page_width / max(len(keys), 1)

        pdf.set_fill_color(200, 220, 255)
        for key in keys:
            pdf.cell(col_width, 8, key, border=1, fill=True)
        pdf.ln()

        for row in data:
            for key in keys:
                val = str(row.get(key, ""))
                if len(val) > 30:
                    val = val[:27] + "..."
                pdf.cell(col_width, 8, val, border=1)
            pdf.ln()

        return pdf.output(dest="S").encode("latin1")  # FPDF already returns str or bytes

    @staticmethod
    def collect_artifacts(test_id: str, student_id: str) -> Dict[str, Optional[str]]:
        folder = os.path.join("uploads", "marked", str(test_id), str(student_id))
        artifacts: Dict[str, Optional[str]] = {
            "feedback_json": None,
            "annotated_image": None,
        }

        if os.path.isdir(folder):
            feedback_path = os.path.join(folder, "feedback.json")
            image_path = os.path.join(folder, "annotated.png")

            if os.path.isfile(feedback_path):
                artifacts["feedback_json"] = feedback_path
            if os.path.isfile(image_path):
                artifacts["annotated_image"] = image_path

        return artifacts

    @staticmethod
    def export_student_zip(
        test_id: str, student_id: str, destination_folder: str
    ) -> Optional[str]:
        artifacts = ExportService.collect_artifacts(test_id, student_id)
        files_to_include = [p for p in artifacts.values() if p]

        if not files_to_include:
            return None

        os.makedirs(destination_folder, exist_ok=True)
        zip_filename = f"student_{student_id}_test_{test_id}.zip"
        zip_path = os.path.join(destination_folder, zip_filename)

        with zipfile.ZipFile(zip_path, "w") as zipf:
            for path in files_to_include:
                arcname = os.path.basename(path)
                zipf.write(path, arcname=arcname)

        return zip_path

    @staticmethod
    def save_export(file_bytes: bytes, filename: str, folder_path: str) -> str:
        os.makedirs(folder_path, exist_ok=True)
        full_path = os.path.join(folder_path, filename)
        with open(full_path, "wb") as f:
            f.write(file_bytes)
        return full_path


# Module-level convenience functions
def export_submissions_to_csv(
    submissions: List[Union[Dict[str, Any], object]], fieldnames: Optional[List[str]] = None
) -> str:
    return ExportService.export_submissions_to_csv(submissions, fieldnames)


def export_submissions_to_pdf(
    submissions: List[Union[Dict[str, Any], object]], title: str = "Submissions Report"
) -> bytes:
    return ExportService.export_submissions_to_pdf(submissions, title)


def export_student_zip(
    test_id: str, student_id: str, destination_folder: str
) -> Optional[str]:
    return ExportService.export_student_zip(test_id, student_id, destination_folder)


def export_override_csv(overrides: List[Dict[str, Any]], output_path: str):
    with open(output_path, "w", newline="") as csvfile:
        fieldnames = ["student_id", "question_id", "old_score", "new_score", "reason"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in overrides:
            writer.writerow(row)


def export_grading_results(test_id: Any) -> List[Dict[str, Any]]:
    from smartscripts.models import Test

    test = Test.query.get(test_id)
    if not test or not getattr(test, "student_scripts", None):
        return []

    data: List[Dict[str, Any]] = []
    for script in test.student_scripts:
        row: Dict[str, Any] = {"Student ID": getattr(script, "student_id", "")}
        for score in getattr(script, "scores", []):
            row[f"Q{getattr(score, 'question_id', '')}"] = getattr(score, "score", "")
        data.append(row)
    return data
