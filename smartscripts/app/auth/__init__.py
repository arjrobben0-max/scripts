from flask import Blueprint
from sqlalchemy.exc import SQLAlchemyError

# Register blueprint independently
auth_bp = Blueprint(
    "auth",  # endpoint prefix will be "auth"
    __name__,
    template_folder="templates",
    url_prefix="/auth"  # ensures routes start with /auth
)

# Import routes after blueprint definition
from . import routes
