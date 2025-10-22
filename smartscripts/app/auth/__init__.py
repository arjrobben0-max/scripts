from flask import Blueprint

# Define the main authentication blueprint
auth_bp = Blueprint(
    "auth_bp",  # endpoint name
    __name__,
    template_folder="templates",
    url_prefix="/auth"
)

# Import routes after defining the blueprint
from . import routes
