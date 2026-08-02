"""
Seed script: Bubur Fay Pilot Setup
Creates Business, Admin User, and 3 Outlets.

Run: python3 scripts/seed_bubur_fay_pilot.py
"""
import sys
sys.path.insert(0, '/home/ubuntu/google-reviews-monitoring')

from app import create_app, db
from app.models.entities import Business, User, Outlet, LocationCandidate
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone
import uuid

app = create_app()

OUTLETS = [
    {
        'name': 'Bubur Fay Caman',
        'address': 'Jl. Caman Raya No.2 Blk A, RT.002/RW.003, Jatibening, Kec. Pd. Gede, Kota Bekasi, Jawa Barat 17412',
        'place_id': '0x2e698d1b2904fd33:0xff5dfeffa01cf5ac',
        'latitude': -6.2588,  # approximate
        'longitude': 106.9035,  # approximate
    },
    {
        'name': 'Bubur Fay Ratna',
        'address': 'Jl. Dr. Ratna No.39 F, RT.001/RW.001, Jatibening, Kec. Pd. Gede, Kota Bekasi, Jawa Barat 17412',
        'place_id': '0x2e698dd9b7c50a85:0x69f5bee9d4f8af7b',
        'latitude': -6.2590,
        'longitude': 106.9020,
    },
    {
        'name': 'Bubur Fay RTM Kelapa Dua',
        'address': 'Jl. Klp. Dua Raya No.37, Tugu, Cimanggis, Depok City, West Java 16451',
        'place_id': '0x2e69ed7da8615457:0xd5faa9e9b51f1867',
        'latitude': -6.3732,
        'longitude': 106.8235,
    },
]

def _uuid():
    return str(uuid.uuid4())

def _now():
    return datetime.now(timezone.utc)

with app.app_context():
    # Idempotent: clean old data first
    print('🧹 Cleaning old Bubur Fay data...')
    old_biz = Business.query.filter_by(tenant_id='bubur-fay').first()
    if old_biz:
        User.query.filter_by(business_id=old_biz.id).delete()
        Outlet.query.filter_by(tenant_id='bubur-fay').delete()
        LocationCandidate.query.filter_by(tenant_id='bubur-fay').delete()
        db.session.delete(old_biz)
        db.session.commit()
        print('   Cleaned old data.')
    else:
        print('   No old data found.')
        db.session.rollback()  # clear the SELECT transaction

    # 1. Create Business (tenant)
    biz = Business(
        id=_uuid(),
        tenant_id='bubur-fay',
        name='Bubur Fay',
        brand_name='Bubur Fay',
        country='ID',
        timezone='Asia/Jakarta',
        default_language='id',
        status='active',
    )
    db.session.add(biz)
    db.session.flush()
    print(f'✅ Business created: Bubur Fay (tenant=bubur-fay, id={biz.id})')

    # 2. Create Admin User
    pw_hash = generate_password_hash('admin123456')
    admin = User(
        id=_uuid(),
        email='admin@bubur-fay.id',
        password_hash=pw_hash,
        display_name='Admin Bubur Fay',
        role='admin',
        is_active=True,
        business_id=biz.id,
    )
    db.session.add(admin)
    print(f'✅ User created: admin@bubur-fay.id / admin123456 (role=admin)')

    # 3. Create 3 Outlets + Candidates
    created_outlets = []
    for o in OUTLETS:
        outlet = Outlet(
            id=_uuid(),
            tenant_id='bubur-fay',
            business_id=biz.id,
            name=o['name'],
            address=o['address'],
            latitude=o['latitude'],
            longitude=o['longitude'],
            public_place_id=o['place_id'],
            gbp_account_id=None,
            gbp_location_id=None,
            owner_verification_status='pending',
            gbp_match_status='unmatched',
            monitor_enabled=True,  # ✅ Active in pilot
            reply_enabled=False,   # ✅ NO auto-reply
            status='active',
        )
        db.session.add(outlet)
        db.session.flush()
        created_outlets.append(outlet)

        # Also add as LocationCandidate for discovery workflows
        candidate = LocationCandidate(
            id=_uuid(),
            tenant_id='bubur-fay',
            business_id=biz.id,
            search_query=o['name'],
            place_id=o['place_id'],
            display_name=o['name'],
            formatted_address=o['address'],
            latitude=o['latitude'],
            longitude=o['longitude'],
            business_status='OPERATIONAL',
            source='owner_input',
            discovery_status='confirmed',
            owner_verification_status='verified',
        )
        db.session.add(candidate)
        print(f'✅ Outlet + Candidate: {o["name"]}')

    db.session.commit()

    # 4. Summary
    print()
    print('═══ Pilot Seed Complete ═══')
    print(f'Business:  {biz.name} (tenant={biz.tenant_id})')
    print(f'Admin:     admin@bubur-fay.id / admin123456')
    print(f'Outlets:   {len(created_outlets)}')
    for o in created_outlets:
        print(f'  - {o.name}')
        print(f'    ID:        {o.id}')
        print(f'    Place ID:  {o.public_place_id}')
        print(f'    Monitor:   {o.monitor_enabled}')
        print(f'    Reply:     {o.reply_enabled}')
    print()
    print('Note: GBP account/location IDs masih kosong — akan diisi via OAuth.')
    print('      Harjamukti excluded (hard rule in feature_flags).')
    print('      auto-reply OFF, reply_enabled=false, approval required.')
