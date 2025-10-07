import ast
import os

MODELS_DIR = r"C:\Users\ALEX\Desktop\Smartscripts\smartscripts\models"

# Store relationships: {ClassName: {attr_name: (target_class, back_populates)}}
relationships = {}

def parse_relationships(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=file_path)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            relationships.setdefault(class_name, {})

            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call):
                            if getattr(stmt.value.func, "id", None) == "relationship":
                                # Extract first argument (target class)
                                if stmt.value.args:
                                    arg0 = stmt.value.args[0]
                                    if isinstance(arg0, ast.Constant):
                                        target_class = arg0.value
                                    elif isinstance(arg0, ast.Str):  # Python <3.8
                                        target_class = arg0.s
                                    else:
                                        target_class = None
                                else:
                                    target_class = None

                                # Skip placeholder relationships
                                if target_class == "??":
                                    continue

                                # Extract back_populates kwarg
                                back_populates = None
                                for kw in stmt.value.keywords:
                                    if kw.arg == "back_populates":
                                        if isinstance(kw.value, ast.Constant):
                                            back_populates = kw.value.value
                                        elif isinstance(kw.value, ast.Str):
                                            back_populates = kw.value.s

                                relationships[class_name][target.id] = (target_class, back_populates)

# Parse all model files
for root, _, files in os.walk(MODELS_DIR):
    for file in files:
        if file.endswith(".py") and not file.startswith("__"):
            parse_relationships(os.path.join(root, file))

# Audit relationships
errors = []
for cls, attrs in relationships.items():
    for attr_name, (target_cls, back_pop) in attrs.items():
        if target_cls:
            # Check if target class exists
            if target_cls not in relationships:
                errors.append(f"[!] Target class '{target_cls}' not found for {cls}.{attr_name}")
                continue

            # Check back_populates exists on the target class
            target_attrs = relationships[target_cls]
            if back_pop:
                if back_pop not in target_attrs:
                    errors.append(
                        f"[!] Back_populates mismatch: {cls}.{attr_name} -> {target_cls}.{back_pop} (attribute not found)"
                    )
            else:
                errors.append(
                    f"[?] Missing back_populates in {cls}.{attr_name} targeting {target_cls}"
                )

# Report
if errors:
    print("⚠️ Inconsistent relationships found:")
    for e in errors:
        print(e)
else:
    print("✅ All relationships back_populates look correct.")
