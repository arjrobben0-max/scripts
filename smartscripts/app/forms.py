# smartscripts/app/forms.py

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired, FileField
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    BooleanField,
    SelectField,
    TextAreaField,
    DateField,
    HiddenField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional


# -----------------------
# Authentication Forms
# -----------------------

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")
    submit = SubmitField("Login")


class RegisterForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=25)],
        render_kw={"placeholder": "Enter your username"},
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email()],
        render_kw={"placeholder": "Enter your email"},
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=6),
            EqualTo("confirm_password", message="Passwords must match"),
        ],
        render_kw={"placeholder": "Create a password"},
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired()],
        render_kw={"placeholder": "Repeat your password"},
    )
    role = SelectField(
        "Role",
        choices=[("student", "Student"), ("teacher", "Teacher")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Register")


class ForgotPasswordForm(FlaskForm):
    """Request password reset by email"""
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    """Reset the user's password using token"""
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match")],
    )
    submit = SubmitField("Reset Password")


# -----------------------
# Teacher Authentication
# -----------------------

class TeacherLoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")
    submit = SubmitField("Teacher Login")


class TeacherRegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=25)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=6),
            EqualTo("confirm_password", message="Passwords must match"),
        ],
    )
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired()])
    role = SelectField(
        "Registering As",
        choices=[("Teacher", "Teacher"), ("Student", "Student")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Register")


# -----------------------
# Test Creation + File Upload
# -----------------------

class TestForm(FlaskForm):
    """Unified form for creating a test and uploading related files."""
    test_title = StringField("Test Title", validators=[DataRequired()])
    
    subject = SelectField(
        "Subject",
        choices=[
            ("math", "Math"),
            ("science", "Science"),
            ("english", "English"),
            ("history", "History"),
            ("geography", "Geography"),
            ("physics", "Physics"),
            ("chemistry", "Chemistry"),
        ],
        validators=[DataRequired()],
    )

    grade_level = SelectField(
        "Grade Level",
        choices=[
            ("9", "9th Grade"),
            ("10", "10th Grade"),
            ("11", "11th Grade"),
            ("12", "12th Grade"),
        ],
        validators=[Optional()],
    )

    exam_date = DateField("Exam Date (optional)", format="%Y-%m-%d", validators=[Optional()])
    description = TextAreaField("Description", validators=[Optional(), Length(max=500)])

    # File uploads
    question_paper = FileField(
        "Question Paper",
        validators=[FileRequired(), FileAllowed(["pdf", "doc", "docx", "txt", "csv"], "Documents only!")],
    )
    rubric = FileField(
        "Rubric",
        validators=[Optional(), FileAllowed(["pdf", "doc", "docx", "txt"], "Documents only!")],
    )
    marking_guide = FileField(
        "Marking Guide",
        validators=[FileRequired(), FileAllowed(["pdf", "doc", "docx", "txt"], "Documents only!")],
    )
    answered_script = FileField(
        "Answered Script",
        validators=[Optional(), FileAllowed(["pdf", "doc", "docx"], "Documents only!")],
    )
    class_list = FileField(
        "Class List",
        validators=[Optional(), FileAllowed(["csv", "txt"], "CSV or TXT only!")],
    )
    combined_scripts = FileField(
        "Combined Scripts",
        validators=[FileRequired(), FileAllowed(["pdf"], "PDF only!")],
    )

    submit = SubmitField("Create Test & Upload Files")


# -----------------------
# AI Grading Form
# -----------------------

class AIGradingForm(FlaskForm):
    submit = SubmitField("Start AI Grading")


# -----------------------
# Bulk Override Upload Form
# -----------------------

class BulkOverrideUploadForm(FlaskForm):
    bulk_file = FileField(
        "Upload CSV or JSON file",
        validators=[FileRequired(), FileAllowed(["csv", "json"], "CSV or JSON files only!")],
    )
    submit = SubmitField("Submit Overrides")


# -----------------------
# File Management (Dashboard)
# -----------------------

class UploadFileForm(FlaskForm):
    file = FileField(
        "Upload File",
        validators=[FileRequired(), FileAllowed(["pdf", "doc", "docx", "txt", "csv"], "Only PDF/DOC/TXT/CSV allowed!")],
    )
    submit = SubmitField("Upload")


class DeleteFileForm(FlaskForm):
    submit = SubmitField("Delete")


# -----------------------
# Preprocessing & Inline Editing
# -----------------------

class PreprocessingForm(FlaskForm):
    submit = SubmitField("Start Preprocessing")


class InlineEditForm(FlaskForm):
    student_id = HiddenField("Student ID")
    name = StringField("Corrected Name", validators=[Optional(), Length(min=2, max=100)])
    student_number = StringField("Corrected Student ID", validators=[Optional(), Length(min=3, max=20)])
    submit = SubmitField("Save Correction")
