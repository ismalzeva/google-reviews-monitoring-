"""Check tables and DB info"""
import sys
sys.path.insert(0, '/home/ubuntu/google-reviews-monitoring')
from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f'Database: {db.engine.url}')
    print(f'Tables ({len(tables)}): {tables}')
    
    for t in tables:
        cols = [c['name'] for c in inspector.get_columns(t)]
        count = db.session.execute(db.text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        print(f'  {t}: {count} rows, columns={cols[:10]}...')
