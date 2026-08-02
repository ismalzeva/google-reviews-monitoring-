"""Check current DB state for GRM"""
import sys
sys.path.insert(0, '/home/ubuntu/google-reviews-monitoring')
from app import create_app, db
from app.models.entities import Business, Outlet, User, LocationCandidate

app = create_app()
with app.app_context():
    businesses = Business.query.all()
    print('=== Businesses ===')
    for b in businesses:
        outlets_count = Outlet.query.filter_by(business_id=b.id).count()
        print(f'  {b.id} | {b.name} | brand={b.brand_name} | tenant={b.tenant_id} | outlets={outlets_count}')
    
    outlets = Outlet.query.all()
    print()
    print('=== Outlets ===')
    for o in outlets:
        print(f'  {o.id} | {o.name} | place_id={o.public_place_id}')
        print(f'    address={o.address}')
        print(f'    gbp_account={o.gbp_account_id} | gbp_location={o.gbp_location_id}')
        print(f'    monitor={o.monitor_enabled} | reply={o.reply_enabled}')
    
    users = User.query.all()
    print()
    print('=== Users ===')
    for u in users:
        print(f'  {u.id} | {u.email} | role={u.role} | business_id={u.business_id}')
    
    candidates = LocationCandidate.query.all()
    print()
    print(f'=== Location Candidates: {len(candidates)} ===')
    for c in candidates:
        print(f'  {c.id[:8]} | {c.display_name} | place_id={c.place_id}')
