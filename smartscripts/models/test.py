import os
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Date, Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from flask import current_app, url_for

from smartscripts.extensions import db


class Test(db.Model):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    subject = Column(String(100), nullable=False)
    exam_date = Column(Date, nullable=False)
    grade_level = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    # ✅ File paths
    question_paper_path = Column(String(255), nullable=True)
    rubric_path = Column(String(255), nullable=True)
    marking_guide_path = Column(String(255), nullable=True)
    answered_script_path = Column(String(255), nullable=True)
    class_list_path = Column(String(255), nullable=True)
    combined_scripts_path = Column(String(255), nullable=True)

    # ✅ OCR task tracking
    ocr_task_id = Column(String(50), nullable=True)

    reviewed_by_teacher = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # --- Relationships ---
    teacher = relationship("User", back_populates="tests")
    scripts = relationship("TestScript", back_populates="test", cascade="all, delete-orphan")
    submissions = relationship("TestSubmission", back_populates="test", cascade="all, delete-orphan")
    student_submissions = relationship("StudentSubmission", back_populates="test")
    marking_guide = relationship("MarkingGuide", back_populates="test", uselist=False)
    override_logs = relationship("OcrOverrideLog", back_populates="test")
    page_reviews = relationship("PageReview", back_populates="test")
    marksheet = relationship("Marksheet", back_populates="test", uselist=False)

    def __init__(self, **kwargs):
        """Allow flexible keyword initialization."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    # --- Path & URL helpers ---
    def _build_url(self, folder: str, filename: str):
        """Build a static URL for uploaded files."""
        if not filename:
            return None
        return url_for("static", filename=f"uploads/{folder}/{self.id}/{filename}")

    # URLs for serving files
    @property
    def question_paper_url(self): return self._build_url("question_papers", self.question_paper_path)
    @property
    def rubric_url(self): return self._build_url("rubrics", self.rubric_path)
    @property
    def marking_guide_url(self): return self._build_url("marking_guides", self.marking_guide_path)
    @property
    def answered_script_url(self): return self._build_url("answered_scripts", self.answered_script_path)
    @property
    def class_list_url(self): return self._build_url("student_lists", self.class_list_path)
    @property
    def combined_scripts_url(self): return self._build_url("combined_scripts", self.combined_scripts_path)

    @property
    def all_required_uploaded(self) -> bool:
        """Check if all critical files for this test are uploaded."""
        required = [
            self.question_paper_path,
            self.rubric_path,
            self.marking_guide_path,
            self.answered_script_path,
            self.class_list_path,
            self.combined_scripts_path,
        ]
        return all(required)

    def __repr__(self):
        date_str = self.exam_date.strftime("%Y-%m-%d") if self.exam_date else "No Date"
        return f"<Test {self.title} on {date_str}>"
