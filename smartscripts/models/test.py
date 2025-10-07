import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from flask import current_app, url_for

from smartscripts.extensions import db


class Test(db.Model):
    __tablename__ = 'tests'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    subject = Column(String(100), nullable=False)
    exam_date = Column(Date, nullable=False)
    grade_level = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    # Filenames only — full paths are dynamically built
    question_paper_filename = Column(String(255), nullable=True)
    rubric_filename = Column(String(255), nullable=True)
    marking_guide_filename = Column(String(255), nullable=True)
    answered_script_filename = Column(String(255), nullable=True)
    class_list_filename = Column(String(255), nullable=True)
    combined_scripts_filename = Column(String(255), nullable=True)

    reviewed_by_teacher = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)

    date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    teacher_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    teacher = relationship('User', back_populates='tests')
    scripts = relationship('TestScript', back_populates='test', cascade="all, delete-orphan")
    submissions = relationship('TestSubmission', back_populates='test', cascade="all, delete-orphan")
    student_submissions = relationship('StudentSubmission', back_populates='test')
    marking_guide = relationship('MarkingGuide', back_populates='test', uselist=False)
    override_logs = relationship('OCROverrideLog', back_populates='test')
    page_reviews = relationship('PageReview', back_populates='test')
    marksheet = relationship('Marksheet', back_populates='test', uselist=False)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    # --- File path properties ---

    @property
    def question_paper_path(self):
        return self._build_path("question_papers", self.question_paper_filename)

    @property
    def rubric_path(self):
        return self._build_path("rubrics", self.rubric_filename)

    @property
    def marking_guide_path(self):
        return self._build_path("marking_guides", self.marking_guide_filename)

    @property
    def answered_script_path(self):
        return self._build_path("answered_scripts", self.answered_script_filename)

    @property
    def class_list_path(self):
        return self._build_path("student_lists", self.class_list_filename)

    @property
    def combined_scripts_path(self):
        return self._build_path("combined_scripts", self.combined_scripts_filename)

    def _build_path(self, folder: str, filename: str):
        if filename:
            upload_base = current_app.config.get("UPLOAD_FOLDER")
            if not upload_base:
                current_app.logger.error("UPLOAD_FOLDER config missing!")
                return None
            return os.path.join(upload_base, folder, str(self.id), filename)
        return None

    # --- URL properties for serving files via Flask static route ---

    @property
    def question_paper_url(self):
        if self.question_paper_filename:
            return url_for(
                'static',
                filename=f'uploads/question_papers/{self.id}/{self.question_paper_filename}'
            )
        return None

    @property
    def rubric_url(self):
        if self.rubric_filename:
            return url_for(
                'static',
                filename=f'uploads/rubrics/{self.id}/{self.rubric_filename}'
            )
        return None

    @property
    def marking_guide_url(self):
        if self.marking_guide_filename:
            return url_for(
                'static',
                filename=f'uploads/marking_guides/{self.id}/{self.marking_guide_filename}'
            )
        return None

    @property
    def answered_script_url(self):
        if self.answered_script_filename:
            return url_for(
                'static',
                filename=f'uploads/answered_scripts/{self.id}/{self.answered_script_filename}'
            )
        return None

    @property
    def class_list_url(self):
        if self.class_list_filename:
            return url_for(
                'static',
                filename=f'uploads/student_lists/{self.id}/{self.class_list_filename}'
            )
        return None

    @property
    def combined_scripts_url(self):
        if self.combined_scripts_filename:
            return url_for(
                'static',
                filename=f'uploads/combined_scripts/{self.id}/{self.combined_scripts_filename}'
            )
        return None

    @property
    def all_required_uploaded(self):
        required_files = [
            self.question_paper_filename,
            self.rubric_filename,
            self.marking_guide_filename,
            self.answered_script_filename,
            self.class_list_filename,
            self.combined_scripts_filename,
        ]
        return all(required_files)

    def __repr__(self):
        date_str = self.exam_date.strftime("%Y-%m-%d") if self.exam_date else "No Date"
        return f"<Test {self.title} on {date_str}>"
