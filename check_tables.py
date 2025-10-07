from sqlalchemy import inspect
from smartscripts.app import create_app, db

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print("All tables:", tables)

    for table in ['extracted_student_script', 'ocr_override_log']:
        if table in tables:
            print(f"✅ Table exists: {table}")
        else:
            print(f"❌ Table missing: {table}")
