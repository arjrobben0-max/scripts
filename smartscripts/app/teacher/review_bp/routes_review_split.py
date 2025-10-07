from __future__ import annotations
from datetime import datetime
from typing import Optional

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    request,
    current_app,
)
from flask_login import login_required, current_user

from smartscripts.extensions import db
from smartscripts.models import Test, PageReview, User
from smartscripts.models.extracted_student_script import ExtractedStudentScript
from smartscripts.utils.permissions import teacher_required
from smartscripts.utils.file_helpers import get_image_path_for_page
from . import review_bp
from .utils import is_teacher_or_admin


def get_student_script_for_page(
    test_id: int, page_num: int
) -> Optional[ExtractedStudentScript]:
    """
    Return the ExtractedStudentScript that contains the given page_num.
    """
    scripts = ExtractedStudentScript.query.filter_by(test_id=test_id).all()
    for s in scripts:
        start = getattr(s, "page_start", 0)
        end = start + getattr(s, "page_count", 1) - 1
        if start <= page_num <= end:
            return s
    return None


def get_next_unreviewed_page(test_id: int, start_page: int = 1) -> Optional[int]:
    """
    Returns the next page number for a test that hasn't been reviewed yet.
    """
    page = start_page
    while True:
        image_path = get_image_path_for_page(test_id, page)
        if not image_path:
            break  # no more pages
        existing_review = PageReview.query.filter_by(
            test_id=test_id, page_number=page
        ).first()
        if not existing_review:
            return page
        page += 1
    return None


@review_bp.route("/review_split/<int:test_id>/<int:page_num>")
@login_required
@teacher_required
def review_split_page(test_id: int, page_num: int):
    test = Test.query.get_or_404(test_id)
    if not is_teacher_or_admin(test):
        abort(403)

    image_path = get_image_path_for_page(test_id, page_num)
    if not image_path:
        flash(f"No image found for page {page_num}", "warning")
        next_page = get_next_unreviewed_page(test_id, start_page=1)
        if next_page:
            return redirect(
                url_for(
                    "review_bp.review_split_page",
                    test_id=test_id,
                    page_num=next_page,
                )
            )
        return redirect(url_for("review_bp.review_test", test_id=test_id))

    prior_review = PageReview.query.filter_by(
        test_id=test_id, page_number=page_num
    ).first()
    prior_user = User.query.get(prior_review.reviewer_id) if prior_review else None

    extracted_script = get_student_script_for_page(test_id, page_num)

    return render_template(
        "teacher/review_split.html",
        test=test,
        page_num=page_num,
        image_path=image_path,
        prior_review=prior_review,
        prior_review_user=prior_user,
        next_page_num=page_num + 1,
        extracted_student_script=extracted_script,
    )


@review_bp.route("/submit_review/<int:test_id>/<int:page_num>", methods=["POST"])
@login_required
@teacher_required
def submit_review(test_id: int, page_num: int):
    test = Test.query.get_or_404(test_id)
    if not is_teacher_or_admin(test):
        abort(403)

    # Decision & comment
    decision = request.form.get("decision", "").strip().lower()
    comment = request.form.get("comment", "").strip()
    is_front_page = decision == "yes"

    # Optional overrides
    student_name_override = request.form.get("matched_name", "").strip()
    student_id_override = request.form.get("matched_id", "").strip()

    # Get the ExtractedStudentScript safely
    script = get_student_script_for_page(test_id, page_num)
    extracted_script_id = script.id if script else None

    # Fetch existing review
    review = PageReview.query.filter_by(
        test_id=test_id, page_number=page_num
    ).first()

    if not review:
        # Create a new PageReview
        review = PageReview(
            test_id=test_id,
            extracted_script_id=extracted_script_id,
            page_number=page_num,
            is_front_page=is_front_page,
            override_name=student_name_override or None,
            override_student_id=student_id_override or None,
            review_comment=comment or None,
            reviewer_id=current_user.id,
            reviewed_at=datetime.utcnow(),
        )
        db.session.add(review)
    else:
        # Update existing review
        review.is_front_page = is_front_page
        review.override_name = student_name_override or None
        review.override_student_id = student_id_override or None
        review.review_comment = comment or None
        review.reviewer_id = current_user.id
        review.reviewed_at = datetime.utcnow()

    # Commit safely
    try:
        db.session.commit()
        flash(f"✅ Review for page {page_num} saved.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[submit_review] DB commit failed: {e}")
        flash(f"❌ Failed to save review: {str(e)}", "danger")

    # Move to next unreviewed page
    next_page = get_next_unreviewed_page(test_id, start_page=page_num + 1)
    if next_page:
        return redirect(
            url_for("review_bp.review_split_page", test_id=test_id, page_num=next_page)
        )

    flash("ℹ️ All pages reviewed or no next page found.", "info")
    return redirect(url_for("review_bp.review_test", test_id=test_id))
