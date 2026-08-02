"""Clean up partial seed from failed run"""
import sys
sys.path.insert(0, '/home/ubuntu/google-reviews-monitoring')
from app import create_app, db
from app.models.entities import Business, User, Outlet, LocationCandidate

app = create_app()
with app.app_context():
    # Find any old Bubur Fay data
    old_biz = Business.query.filter_by(tenant_id='bubur-fay').first()
    if old_biz:
        User.query.filter_by(business_id=old_biz.id).delete()
        Outlet.query.filter_by(tenant_id='bubur-fay').delete()
        LocationCandidate.query.filter_by(tenant_id='bubur-fay').delete()
        db.session.delete(old_biz)
        db.session.commit()
        print('✅ Cleaned partial seed data')
    else:
        print('No stale data found')
