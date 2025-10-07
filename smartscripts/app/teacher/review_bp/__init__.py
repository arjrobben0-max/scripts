from flask import Blueprint

# Blueprint for all review-related routes
review_bp = Blueprint("review_bp", __name__, url_prefix="/teacher/review")

# Import route modules to register their routes with review_bp
from . import (
    routes_review_test,
    routes_review_split,
    routes_overrides,
    routes_files,
    routes_ai_grading,
)

# Optional: import utility functions for easier access
from . import utils
