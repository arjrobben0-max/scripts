# smartscripts/app/teacher/utils.py
import csv
from fuzzywuzzy import process
import os
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app, Blueprint

from smartscripts.models import Student

# === Flask Blueprint ===
utils_bp = Blueprint("utils_bp", __name__)

# === File Handling Config (maps to config.py) ===
UPLOAD_FOLDERS = {
    "question_paper": "QUESTION_PAPER_FOLDER",
    "rubric": "RUBRIC_FOLDER",
    "marking_guide": "MARKING_GUIDE_FOLDER",
    "answered_script": "ANSWERED_SCRIPTS_FOLDER",
    "class_list": "STUDENT_LIST_FOLDER",
    "combined_scripts": "COMBINED_SCRIPTS_FOLDER",
}

FILENAME_FIELDS = {
    "question_paper": "question_paper_filename",
    "rubric": "rubric_filename",
    "marking_guide": "marking_guide_filename",
    "answered_script": "answered_script_filename",
    "class_list": "class_list_filename",
    "combined_scripts": "combined_scripts_filename",
}

# === File Upload Helpers ===
def allowed_file(filename: str) -> bool:
    allowed_extensions = {"pdf", "csv", "txt", "zip"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_uploaded_file(file, folder_key: str, test_id: int, filename: str | None = None) -> str:
    if folder_key not in UPLOAD_FOLDERS:
        raise ValueError(f"Unknown folder key: {folder_key}")

    if not filename:
        filename = secure_filename(file.filename)

    base_folder: Path = current_app.config[UPLOAD_FOLDERS[folder_key]]
    upload_dir = base_folder / str(test_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / filename
    file.save(file_path)

    rel_path = file_path.relative_to(current_app.config["UPLOAD_FOLDER"])
    return str(rel_path).replace(os.path.sep, "/")


def get_file_path(test_id: int, file_type: str) -> str | None:
    if file_type not in UPLOAD_FOLDERS:
        raise ValueError(f"Unknown file type: {file_type}")

    base_folder: Path = current_app.config[UPLOAD_FOLDERS[file_type]]
    dir_path = base_folder / str(test_id)

    if not dir_path.exists():
        return None

    files = list(dir_path.iterdir())
    if not files:
        return None

    return str(files[0])


def to_static_url(file_path: str | None) -> str | None:
    if not file_path:
        return None

    static_dir = current_app.config["STATIC_FOLDER"]
    rel_path = Path(file_path).relative_to(static_dir)
    return f"/static/{rel_path.as_posix()}"


# === CSV / Class List Helpers ===
def parse_class_list(file_path: str) -> list[dict]:
    students: list[dict] = []
    if not file_path or not os.path.exists(file_path):
        return students

    ext = file_path.rsplit(".", 1)[1].lower()
    delimiter = "," if ext == "csv" else "\t"

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            if "name" in row and "id" in row:
                students.append({"name": row["name"].strip(), "student_id": row["id"].strip()})
    return students


def generate_presence_table(detected_students: list[dict], class_list_students: list[dict]):
    matched = []
    unmatched = []

    class_lookup = {s["student_id"]: s["name"] for s in class_list_students}

    for student in detected_students:
        detected_id = student.get("detected_id")
        detected_name = student.get("detected_name")
        if detected_id in class_lookup:
            matched.append({
                "student_name": class_lookup[detected_id],
                "student_id": detected_id,
                "pdf_path": student.get("pdf_path"),
                "confidence_score": student.get("combined_score", 0.0),
            })
        else:
            unmatched.append({
                "student_name": detected_name,
                "student_id": detected_id,
                "pdf_path": student.get("pdf_path"),
                "confidence_score": student.get("combined_score", 0.0),
            })
    return matched, unmatched


def read_csv_for_presence(csv_path: str) -> list[dict]:
    records = []
    if not csv_path or not os.path.exists(csv_path):
        return records

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records.extend(reader)
    return records


def save_presence_csv(records: list[dict], output_path: str) -> None:
    if not records:
        return

    fieldnames = records[0].keys()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def match_name_id_to_classlist(ocr_result: dict, class_list: list[dict]) -> tuple[dict | None, float]:
    ocr_id = ocr_result.get("id", "").strip()
    ocr_name = ocr_result.get("name", "").strip()

    class_ids = [s["student_id"] for s in class_list]
    class_names = [s["name"] for s in class_list]
    class_dict_by_id = {s["student_id"]: s["name"] for s in class_list}
    class_dict_by_name = {s["name"]: s["student_id"] for s in class_list}

    if ocr_id:
        best_id_match, id_score = process.extractOne(ocr_id, class_ids) or (None, 0)
        id_conf = id_score / 100.0
        if id_conf >= 0.7:
            return {"id": best_id_match, "name": class_dict_by_id[best_id_match]}, id_conf

    if ocr_name:
        best_name_match, name_score = process.extractOne(ocr_name, class_names) or (None, 0)
        name_conf = name_score / 100.0
        if name_conf >= 0.7:
            return {"id": class_dict_by_name[best_name_match], "name": best_name_match}, name_conf

    return None, 0.0
