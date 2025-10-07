"""
check_relationships.py
----------------------
Utility script to scan all SQLAlchemy models in Smartscripts
and detect missing or inconsistent relationships or back_populates.
Compatible with SQLAlchemy 2.x and Flask-SQLAlchemy 3.x.
"""

import os
import sys
import importlib
from sqlalchemy.orm import class_mapper
from sqlalchemy.exc import NoForeignKeysError

# --- Ensure project root is on sys.path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# --- Import Flask app and database ---
from smartscripts import create_app
from smartscripts.extensions import db

# --- Initialize app context ---
app = create_app()
app.app_context().push()


def import_all_models():
    """
    Dynamically import all model files from smartscripts/models.
    This ensures every model class is registered before scanning.
    """
    models_dir = os.path.join(BASE_DIR, "smartscripts", "models")
    package_prefix = "smartscripts.models"

    for filename in os.listdir(models_dir):
        if filename.endswith(".py") and filename not in ("__init__.py",):
            module_name = f"{package_prefix}.{filename[:-3]}"
            try:
                importlib.import_module(module_name)
            except Exception as e:
                print(f"⚠️ Failed to import {module_name}: {e}")

    # Collect all declared mappers (SQLAlchemy 2.x+)
    return [mapper.class_ for mapper in db.Model.registry.mappers]


def check_back_populates(models):
    """Check that all relationships have consistent back_populates definitions."""
    issues = []

    for model in models:
        try:
            mapper = class_mapper(model)
        except Exception as e:
            issues.append(f"⚠️ Could not map {model.__name__}: {e}")
            continue

        for rel in mapper.relationships:
            if not rel.back_populates:
                continue  # skip relationships that don't use back_populates

            target = rel.entity.entity

            try:
                target_mapper = class_mapper(target)
                reciprocal = None
                for r in target_mapper.relationships:
                    if r.entity.entity == model and r.back_populates == rel.key:
                        reciprocal = r
                        break

                if not reciprocal:
                    issues.append(
                        f"🔁 In {model.__name__}.{rel.key}: "
                        f"back_populates='{rel.back_populates}' has no reciprocal on {target.__name__}"
                    )

            except Exception as e:
                issues.append(
                    f"⚠️ Could not inspect target {target.__name__} from {model.__name__}.{rel.key}: {e}"
                )

    return issues


def check_foreign_keys(models):
    """Check that all relationships have proper foreign keys defined."""
    issues = []

    for model in models:
        try:
            mapper = class_mapper(model)
        except Exception as e:
            issues.append(f"⚠️ Could not map {model.__name__}: {e}")
            continue

        for rel in mapper.relationships:
            try:
                _ = rel.primaryjoin  # triggers check
            except NoForeignKeysError:
                issues.append(
                    f"❌ No foreign keys between {model.__name__} and {rel.entity.entity.__name__} "
                    f"for relationship '{rel.key}'"
                )

    return issues


if __name__ == "__main__":
    print("🔍 Scanning models for relationship consistency...\n")
    models = import_all_models()

    back_pop_issues = check_back_populates(models)
    fk_issues = check_foreign_keys(models)

    all_issues = back_pop_issues + fk_issues

    if all_issues:
        print("🚨 Inconsistencies found:\n")
        for issue in all_issues:
            print(" -", issue)
    else:
        print("✅ All relationships and back_populates look consistent!")

    print("\n✅ Scan complete.")
