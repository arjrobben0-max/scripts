# check_back_populates.py
import importlib
import pkgutil
from sqlalchemy.orm import class_mapper, RelationshipProperty
from sqlalchemy.exc import InvalidRequestError
from smartscripts.extensions import db
import smartscripts.models

def get_all_models(package):
    """Dynamically import all modules in a package and collect db.Model subclasses."""
    models = []
    for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
        if not is_pkg:
            module = importlib.import_module(f"{package.__name__}.{module_name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                try:
                    if isinstance(attr, type) and issubclass(attr, db.Model) and attr is not db.Model:
                        models.append(attr)
                except TypeError:
                    pass
    return models

def check_back_populates(models):
    """Check for incorrect back_populates in all models."""
    errors = []

    for model in models:
        try:
            mapper = class_mapper(model)
        except InvalidRequestError as e:
            errors.append(f"⚠️ Could not map model {model.__name__}: {e}")
            continue

        for prop in mapper.iterate_properties:
            if isinstance(prop, RelationshipProperty):
                target_model = prop.mapper.class_
                back_name = prop.back_populates
                if back_name:
                    if not hasattr(target_model, back_name):
                        errors.append(
                            f"In {model.__name__}.{prop.key}: back_populates='{back_name}' "
                            f"does NOT exist in {target_model.__name__}"
                        )
    return errors

if __name__ == "__main__":
    print("🔎 Scanning all models for back_populates inconsistencies...\n")
    all_models = get_all_models(smartscripts.models)
    issues = check_back_populates(all_models)

    if issues:
        print("❌ Found inconsistent back_populates:\n")
        for e in issues:
            print(" -", e)
    else:
        print("✅ All back_populates are consistent!")
