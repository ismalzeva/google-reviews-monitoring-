"""Check all stale data"""
import sys
sys.path.insert(0, '/home/ubuntu/google-reviews-monitoring')
from app import create_app, db
from app.models.entities import Business, User, Outlet, LocationCandidate

app = create_app()
with app.app_context():
    for table_name, model in [('Business', Business), ('User', User), ('Outlet', Outlet), ('LocationCandidate', LocationCandidate)]:
        rows = model.query.all()
        print(f'{table_name}: {len(rows)} rows')
        for r in rows:
            if hasattr(r, 'tenant_id'):
                print(f'  {r.id} | tenant={r.tenant_id} | name={getattr(r, "name", "")}')
            elif hasattr(r, 'email'):
                print(f'  {r.id} | email={r.email}')
            else:
                print(f'  {r.id}')
