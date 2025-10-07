import os
import csv
import argparse
from rapidfuzz import fuzz, process  # ✅ Fuzzy matching
from smartscripts.app import create_app  # ✅ Bootstrap Flask + DB
from smartscripts.services.bulk_upload_service import store_attendance_records
from smartscripts.ai.text_matching import load_class_list

def load_extracted_ids(txt_path: str):
    """Load OCR-extracted student IDs from a plain text file (one per line)."""
    with open(txt_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def match_ocr_ids_to_class(extracted_ids, class_list, threshold: int = 80):
    """
    Match OCR-extracted IDs against class list using fuzzy matching.
    Returns (matched_ids, unmatched_ids)
    matched_ids is a dict {ocr_id: {"student": student_dict, "score": score}}
    """
    student_ids = [s["student_id"] for s in class_list]
    matched = {}
    unmatched = []

    for ocr_id in extracted_ids:
        best_match = process.extractOne(
            ocr_id,
            student_ids,
            scorer=fuzz.ratio
        )
        if best_match and best_match[1] >= threshold:
            matched[ocr_id] = {
                "student": next(
                    s for s in class_list if s["student_id"] == best_match[0]
                ),
                "score": best_match[1]
            }
        else:
            unmatched.append(ocr_id)

    return matched, unmatched


def main():
    parser = argparse.ArgumentParser(
        description="Generate and store attendance records from OCR + class list"
    )
    parser.add_argument(
        "--test-id",
        required=True,
        help="Test ID to associate records with (must exist in DB)"
    )
    parser.add_argument(
        "--class-list",
        required=True,
        help="Path to class list CSV (must include 'student_id' and 'name' columns)"
    )
    parser.add_argument(
        "--ocr-ids",
        required=True,
        help="Path to TXT file containing OCR-extracted student IDs (one per line)"
    )

    args = parser.parse_args()

    # Load input files
    class_list = load_class_list(args.class_list)
    extracted_ids = load_extracted_ids(args.ocr_ids)

    # Perform fuzzy/heuristic matching
    matched_ids, unmatched_ids = match_ocr_ids_to_class(extracted_ids, class_list)

    # Console output
    print(f"\n✅ Matched: {len(matched_ids)} IDs")
    print(f"❌ Unmatched: {len(unmatched_ids)} IDs\n")

    if matched_ids:
        print("📌 Match Details:")
        for ocr_id, data in matched_ids.items():
            student = data["student"]
            score = data["score"]
            print(f" - OCR '{ocr_id}' → {student['student_id']} ({student['name']}) "
                  f"[Confidence: {score}%]")

    if unmatched_ids:
        print("\n⚠️ Unmatched OCR IDs:")
        for uid in unmatched_ids:
            print(f" - {uid}")

    # Persist attendance records
    store_attendance_records(
        test_id=args.test_id,
        class_list=class_list,
        matched_ids=set([s["student"]["student_id"] for s in matched_ids.values()])
    )

    print(f"\n📋 Attendance records saved for test {args.test_id}")


if __name__ == "__main__":
    # ✅ Ensure Flask app + DB context are active
    app = create_app()
    with app.app_context():
        main()
