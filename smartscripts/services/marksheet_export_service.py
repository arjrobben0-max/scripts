# File: smartscripts/services/export_service.py

import os
import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

LOGO_PATH = Path("static/overlays/logo.png")  # optional PDF header logo


class ExportService:
    """
    Unified service for exporting student test results:
    - CSV marksheet
    - JSON feedback + annotations
    - PDF summary report
    """

    def __init__(self, base_export_dir: Path = Path("uploads/final_exports")):
        self.base_export_dir = base_export_dir
        self.base_export_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------
    # Public API
    # ------------------------
    def export_student_results(
        self,
        test_id: str,
        student_id: str,
        marks_data: Dict[str, Any],
        feedback_data: Dict[str, Any],
        annotations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Path]:
        """
        Export marksheet CSV, feedback JSON, and PDF summary for a single student.
        Returns paths to all exported files.
        """
        student_export_dir = self.base_export_dir / test_id / student_id
        student_export_dir.mkdir(parents=True, exist_ok=True)

        # Export CSV
        csv_path = student_export_dir / "final_marksheet.csv"
        self._export_csv(csv_path, marks_data)

        # Export JSON
        json_path = student_export_dir / "final_feedback.json"
        self._export_json(
            json_path,
            {
                "marks": marks_data,
                "feedback": feedback_data,
                "annotations": annotations or [],
            },
        )

        # Export PDF summary
        pdf_path = student_export_dir / "final_marked.pdf"
        self._export_pdf(pdf_path, test_id, student_id, marks_data, feedback_data)

        return {"csv": csv_path, "json": json_path, "pdf": pdf_path}

    # ------------------------
    # Internal helpers
    # ------------------------
    def _export_csv(self, csv_path: Path, marks_data: Dict[str, Any]) -> None:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Question", "Mark"])
            for question, mark in marks_data.items():
                writer.writerow([question, mark])

    def _export_json(self, json_path: Path, data: Dict[str, Any]) -> None:
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def _export_pdf(
        self,
        pdf_path: Path,
        test_id: str,
        student_id: str,
        marks_data: Dict[str, Any],
        feedback_data: Any,
    ) -> None:
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        width, height = letter

        # Optional logo
        if LOGO_PATH.exists():
            c.drawImage(str(LOGO_PATH), x=50, y=height - 80, width=100, height=30)

        c.setFont("Helvetica-Bold", 16)
        title_y = height - 50 if not LOGO_PATH.exists() else height - 90
        c.drawString(50, title_y, "Marksheet Summary")

        c.setFont("Helvetica", 12)
        c.drawString(50, title_y - 20, f"Test ID: {test_id}")
        c.drawString(50, title_y - 40, f"Student ID: {student_id}")

        # Marks section
        y = title_y - 80
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Marks Obtained:")
        y -= 20
        c.setFont("Helvetica", 12)
        for q, mark in marks_data.items():
            c.drawString(60, y, f"{q}: {mark}")
            y -= 20
            if y < 80:
                c.showPage()
                y = height - 50

        # Feedback section
        y -= 10
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Feedback:")
        y -= 20

        c.setFont("Helvetica", 12)
        feedback_texts: List[str] = []
        if isinstance(feedback_data, dict):
            for val in feedback_data.values():
                if isinstance(val, list):
                    feedback_texts.extend(val)
                else:
                    feedback_texts.append(str(val))
        elif isinstance(feedback_data, list):
            feedback_texts = feedback_data
        else:
            feedback_texts = [str(feedback_data)]

        for line in feedback_texts:
            if y < 80:
                c.showPage()
                y = height - 50
            c.drawString(60, y, f"- {line}")
            y -= 18

        c.save()


# ------------------------
# Module-level instance for convenience
# ------------------------
_export_service = ExportService()


def export_student_results(
    test_id: str,
    student_id: str,
    marks_data: dict,
    feedback_data: dict,
    annotations: Optional[list] = None,
) -> Dict[str, Path]:
    return _export_service.export_student_results(
        test_id=test_id,
        student_id=student_id,
        marks_data=marks_data,
        feedback_data=feedback_data,
        annotations=annotations,
    )
