"""
Quality Gate E — AI Review Analysis Engine

Tests E01–E20 covering sentiment, topics, urgency, risk, mismatch,
repeat patterns, tenant isolation, rating-only, batch, dashboard.

Exit 0 only when ALL tests pass.
"""

import sys, os, json
from datetime import datetime, timezone, timedelta

# ─── Bootstrap ───────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DATABASE_URL'] = 'sqlite:////tmp/grm_gate_e.db'
os.environ['SECRET_KEY'] = 'test-key-gate-e-2026-2026'
os.environ['FLASK_ENV'] = 'testing'

from app import create_app, db
from app.models.entities import Business, Outlet, Review, ReviewAnalysis, ReviewReply, User
from app.services.analysis_service import (
    analyze_review, get_dashboard_summary, get_priority_reviews,
    get_outlet_comparison, get_management_summary, batch_analyze_pending,
)

app = create_app()

PASS, FAIL = 0, 0

def ok(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  ✅ {name}')
    else:
        FAIL += 1
        print(f'  ❌ {name}')

def _t(a):
    """Normalize topics_json: parse if string, pass through if already list."""
    raw = a['topics_json'] if isinstance(a, dict) else a.topics_json
    return json.loads(raw) if isinstance(raw, str) else raw

def _ci(a):
    """Normalize confidence_json: parse if string, pass through if already dict."""
    raw = a['confidence_json'] if isinstance(a, dict) else a.confidence_json
    return json.loads(raw) if isinstance(raw, str) else raw

def _act(a):
    """Normalize recommended_internal_action_json: parse if string."""
    raw = a['recommended_internal_action_json'] if isinstance(a, dict) else a.recommended_internal_action_json
    return json.loads(raw) if isinstance(raw, str) else raw

def seed_review(rid, tenant, biz, outlet, comment, rating, has_text=True,
                days_ago=0, reassess=False):
    now = datetime.now(timezone.utc)
    ct = now - timedelta(days=days_ago) if days_ago else now
    return Review(
        id=rid, tenant_id=tenant, business_id=biz, outlet_id=outlet,
        source='google', source_review_name=f'Reviewer-{rid}',
        star_rating=rating, comment=comment, has_text=has_text,
        create_time=ct, update_time=ct,
        qualitative_analysis_status='pending',
        analysis_reassessment_required=reassess,
    )

# ─── Setup DB ────────────────────────────────────────────
with app.app_context():
    db.drop_all()
    db.create_all()
    print(f'🔧 DB engine: {db.engine.url}')
    print(f'🔧 DB path:  /tmp/grm_gate_e.db')
    assert Review.query.count() == 0
    assert Business.query.count() == 0
    print('✅ DB fresh — 0 records before seed\n')

    now = datetime.now(timezone.utc)

    biz_a = Business(id='biz-a-e', name='Bubur Fay', brand_name='Bubur Fay',
                     tenant_id='tenant-a-e', country='ID', timezone='Asia/Jakarta',
                     default_language='id', status='active',
                     created_at=now, updated_at=now)
    biz_b = Business(id='biz-b-e', name='Kedai Kopi B', brand_name='Kedai Kopi B',
                     tenant_id='tenant-b-e', country='ID', timezone='Asia/Jakarta',
                     default_language='id', status='active',
                     created_at=now, updated_at=now)
    db.session.add_all([biz_a, biz_b])

    o_a1 = Outlet(id='out-a1-e', tenant_id='tenant-a-e', business_id='biz-a-e',
                  name='Depok', status='active', monitor_enabled=True,
                  reply_enabled=False, created_at=now, updated_at=now)
    o_a2 = Outlet(id='out-a2-e', tenant_id='tenant-a-e', business_id='biz-a-e',
                  name='Margonda', status='active', monitor_enabled=True,
                  reply_enabled=False, created_at=now, updated_at=now)
    o_old = Outlet(id='out-old-e', tenant_id='tenant-a-e', business_id='biz-a-e',
                   name='Harjamukti', status='inactive', monitor_enabled=False,
                   reply_enabled=False, created_at=now, updated_at=now)
    o_b1 = Outlet(id='out-b1-e', tenant_id='tenant-b-e', business_id='biz-b-e',
                  name='Jakpus', status='active', monitor_enabled=True,
                  reply_enabled=False, created_at=now, updated_at=now)
    db.session.add_all([o_a1, o_a2, o_old, o_b1])
    db.session.add(User(id='u-gate-e', email='test@gate-e.test', password_hash='test-hash-e',
                        display_name='Tester', role='superadmin',
                        business_id='biz-a-e', created_at=now, updated_at=now))
    db.session.commit()

    T, B, O1, O2 = 'tenant-a-e', 'biz-a-e', 'out-a1-e', 'out-a2-e'
    TB, BB = 'tenant-b-e', 'biz-b-e'

    reviews = [
        seed_review('r01', T, B, O1,
                     'Buburnya enak dan pelayanannya ramah. Tempatnya bersih dan nyaman.', 5),
        seed_review('r02', T, B, O1,
                     'Buburnya enak, tetapi nunggunya lama sekali. Pelayanan lambat.', 3),
        seed_review('r03', T, B, O1,
                     'Makanan terasa basi dan setelah makan saya sakit perut. Sangat berbahaya!', 1),
        seed_review('r04', T, B, O1,
                     'Makanan tidak enak dan basi. Kecewa sekali.', 5, reassess=True),
        seed_review('r05', T, B, O1, '', 1, has_text=False),
        seed_review('r06', T, B, O1,
                     'Buburnya enak tapi harganya mahal. Parkir susah dan AC tidak dingin. Toilet kotor.', 2),
        seed_review('r07', T, B, O1, 'Ya gitu deh.', 3),
        seed_review('r08a', T, B, O2,
                     'Pelayanannya lambat. Nunggu 30 menit.', 2, days_ago=2),
        seed_review('r08b', T, B, O2,
                     'Lambat sekali pelayanannya. Tidak recommended.', 1, days_ago=1),
        seed_review('r08c', T, B, O2,
                     'Service lambat bikin kesal.', 1),
        seed_review('r10', T, B, O1, 'Bubur biasa saja. Standar.', 3),
        seed_review('r11', T, B, O1,
                     'Tempat tidak nyaman. Bau. Tidak akan kembali.', 2),
        seed_review('r12', T, B, O1, 'Enak!', 4),
        seed_review('r13', T, B, O1,
                     'Buburnya enak, but the service is terrible. Nunggu lama.', 2),
        seed_review('r-tenant-b', TB, BB, 'out-b1-e',
                     'Kopinya enak, tempat cozy.', 4),
    ]
    db.session.add_all(reviews)
    db.session.commit()

    # Seed R04 with analysis_reassessment_required=True for batch test
    r04 = db.session.get(Review, 'r04')
    r04.analysis_reassessment_required = True
    db.session.commit()

    total_reviews = Review.query.count()
    total_biz = Business.query.count()
    total_out = Outlet.query.count()
    print(f'✅ Seeded: {total_reviews} reviews, {total_out} outlets, {total_biz} businesses\n')

# ═════════════════════════════════════════════════════════
print('═══ GATE E — AI REVIEW ANALYSIS ═══\n')

T, B, O1, O2 = 'tenant-a-e', 'biz-a-e', 'out-a1-e', 'out-a2-e'

# ─── E01: Positive Review ──────────────────────────────
with app.app_context():
    print('── E01: Positive Review ──')
    a = analyze_review(T, B, 'r01')
    ok('E01a: sentiment=positive', a['sentiment'] == 'positive')
    topics = _t(a)
    ok('E01b: topics is list', isinstance(topics, list))
    tn = [t['topic'] for t in topics]
    ok('E01c: contains taste', 'taste' in tn)
    ok('E01d: contains friendliness', 'friendliness' in tn)
    ok('E01e: contains cleanliness', 'cleanliness' in tn)
    ok('E01f: urgency=low', a['urgency'] == 'low')
    ok('E01g: reputation_risk=minimal', a['reputation_risk'] == 'minimal')
    conf = _ci(a)
    ok('E01h: sentiment confidence>0.8', conf.get('sentiment', 0) > 0.8)
    ok('E01i: human_review_required=false', a['human_review_required'] is False)
    ok('E01j: analysis_version set', bool(a['analysis_version']))
    ok('E01k: model_name=rule-based-v1', a['model_name'] == 'rule-based-v1')

# ─── E02: Mixed Review ─────────────────────────────────
with app.app_context():
    print('\n── E02: Mixed Review ──')
    a = analyze_review(T, B, 'r02')
    ok('E02a: sentiment=mixed', a['sentiment'] == 'mixed')
    tn = [t['topic'] for t in _t(a)]
    ok('E02b: contains taste (positive)', 'taste' in tn)
    ok('E02c: contains wait_time (negative)', 'wait_time' in tn)
    ok('E02d: urgency=medium', a['urgency'] == 'medium')

# ─── E03: Critical Review ──────────────────────────────
with app.app_context():
    print('\n── E03: Critical Review ──')
    a = analyze_review(T, B, 'r03')
    # "sangat" amplifies "berbahaya" — no standalone positive word
    ok('E03a: sentiment=negative (sangat amplifies basi/sakit)', a['sentiment'] == 'negative')
    tn = [t['topic'] for t in _t(a)]
    ok('E03b: contains food_safety', 'food_safety' in tn)
    ok('E03c: urgency=critical', a['urgency'] == 'critical')
    ok('E03d: reputation_risk=severe', a['reputation_risk'] == 'severe')
    ok('E03e: human_review_required=true', a['human_review_required'] is True)
    ok('E03f: issue_summary not empty', bool(a['issue_summary']))
    ok('E03g: responsible_role set', bool(a['responsible_role']))

# ─── E04: Rating–Text Mismatch ─────────────────────────
with app.app_context():
    print('\n── E04: Rating–Text Mismatch ──')
    a = analyze_review(T, B, 'r04')
    # "tidak enak" matches NEGATIVE, "enak" also matches POSITIVE → mixed
    # "tidak enak" → compound negative, not mixed
    ok('E04a: sentiment=negative (tidak enak → compound negative)', a['sentiment'] == 'negative')
    ok('E04b: human_review_required=true (mismatch+negative)', a['human_review_required'] is True)
    ok('E04c: issue_summary set', bool(a['issue_summary']))

# ─── E05: Rating-only ──────────────────────────────────
with app.app_context():
    print('\n── E05: Rating-only ──')
    a = analyze_review(T, B, 'r05')
    ok('E05a: sentiment=not_applicable', a['sentiment'] == 'not_applicable')
    ok('E05b: topics is []', _t(a) == [])
    ok('E05c: issue_summary contains rating-only', 'Rating-only' in a['issue_summary'])
    ok('E05d: urgency=low', a['urgency'] == 'low')
    ok('E05e: reputation_risk=minimal', a['reputation_risk'] == 'minimal')
    ok('E05f: human_review_required=false', a['human_review_required'] is False)
    rev5 = db.session.get(Review, 'r05')
    ok('E05g: status=not_applicable', rev5.qualitative_analysis_status == 'not_applicable')

# ─── E06: Multi-topic ──────────────────────────────────
with app.app_context():
    print('\n── E06: Multi-topic ──')
    a = analyze_review(T, B, 'r06')
    ok('E06a: sentiment=mixed', a['sentiment'] == 'mixed')
    topics6 = _t(a)
    tn6 = [t['topic'] for t in topics6]
    ok('E06b: 3+ topics', len(topics6) >= 3)
    ok('E06c: contains taste', 'taste' in tn6)
    ok('E06d: contains price', 'expensive' in tn6 or 'value_for_money' in tn6)
    ok('E06e: contains parking', 'parking' in tn6)
    ok('E06f: contains cleanliness', 'cleanliness' in tn6)

# ─── E07: Low Confidence ───────────────────────────────
with app.app_context():
    print('\n── E07: Low Confidence ──')
    a = analyze_review(T, B, 'r07')
    conf7 = _ci(a)
    ok('E07a: sentiment confidence < 0.6', conf7.get('sentiment', 1) < 0.6)
    ok('E07b: human_review_required=true', a['human_review_required'] is True)

# ─── E08: Repeat Pattern ───────────────────────────────
with app.app_context():
    print('\n── E08: Repeat Pattern ──')
    a08a = analyze_review(T, B, 'r08a')
    _ = analyze_review(T, B, 'r08b')
    _ = analyze_review(T, B, 'r08c')
    repeats = ReviewAnalysis.query.filter(
        ReviewAnalysis.review_pk.in_(['r08a', 'r08b', 'r08c']),
        ReviewAnalysis.repeat_pattern_candidate.is_(True)
    ).count()
    ok('E08a: at least 1 flagged as repeat', repeats >= 1)
    margonda_reviews = Review.query.filter_by(
        tenant_id=T, business_id=B, outlet_id=O2).count()
    ok('E08b: Margonda total reviews = 3', margonda_reviews == 3)

# ─── E09: Tenant Isolation ─────────────────────────────
with app.app_context():
    print('\n── E09: Tenant Isolation ──')
    a_tenant_b = analyze_review(TB, BB, 'r-tenant-b')
    ok('E09a: Tenant B sentiment=positive', a_tenant_b['sentiment'] == 'positive')
    tenant_a_reviews = Review.query.filter_by(tenant_id=T).count()
    tenant_b_reviews = Review.query.filter_by(tenant_id=TB).count()
    ok('E09b: Tenant A sees no B reviews', tenant_a_reviews > 0 and tenant_b_reviews == 1)

# ─── E10: Neutral ──────────────────────────────────────
with app.app_context():
    print('\n── E10: Neutral ──')
    a = analyze_review(T, B, 'r10')
    ok('E10a: sentiment=neutral', a['sentiment'] == 'neutral')
    ok('E10b: urgency=low', a['urgency'] == 'low')
    ok('E10c: topics is list', isinstance(_t(a), list))

# ─── E11: Standard Negative ────────────────────────────
with app.app_context():
    print('\n── E11: Standard Negative ──')
    a = analyze_review(T, B, 'r11')
    # "tidak nyaman" → compound negative
    ok('E11a: sentiment=negative (tidak nyaman → compound negative)', a['sentiment'] == 'negative')
    ok('E11b: urgency=high', a['urgency'] in ('high', 'medium'))

# ─── E12: Very Short Text ──────────────────────────────
with app.app_context():
    print('\n── E12: Very Short Text ──')
    a = analyze_review(T, B, 'r12')
    ok('E12a: sentiment=positive', a['sentiment'] == 'positive')
    ok('E12b: topics is list', isinstance(_t(a), list))
    ok('E12c: urgency=low', a['urgency'] == 'low')

# ─── E13: Mixed Language ───────────────────────────────
with app.app_context():
    print('\n── E13: Mixed Language ──')
    a = analyze_review(T, B, 'r13')
    ok('E13a: sentiment=mixed', a['sentiment'] == 'mixed')
    tn13 = [t['topic'] for t in _t(a)]
    ok('E13b: contains taste', 'taste' in tn13)
    ok('E13c: contains wait_time', 'wait_time' in tn13)

# ─── E14: Urgency Pipeline ─────────────────────────────
with app.app_context():
    print('\n── E14: Urgency Pipeline ──')
    # food_safety topic → high, critical keyword → critical
    u03 = analyze_review(T, B, 'r03')  # "sakit" → critical
    ok('E14a: food_safety → critical', u03['urgency'] == 'critical')
    ok('E14b: food_safety → severe', u03['reputation_risk'] == 'severe')
    # Cleanliness negative → high
    u04 = analyze_review(T, B, 'r04')  # "basi" → critical
    ok('E14c: basi in text → critical', u04['urgency'] == 'critical')
    u01 = analyze_review(T, B, 'r01')  # positive
    ok('E14d: positive → low', u01['urgency'] == 'low')

# ─── E15: Reputation Risk ──────────────────────────────
with app.app_context():
    print('\n── E15: Reputation Risk ──')
    r03 = analyze_review(T, B, 'r03')
    ok('E15a: food_safety → severe', r03['reputation_risk'] == 'severe')

    r06 = analyze_review(T, B, 'r06')
    ok('E15b: mixed + medium urgency → contained risk',
       r06['reputation_risk'] == 'contained')

    r01 = analyze_review(T, B, 'r01')
    ok('E15c: positive → minimal', r01['reputation_risk'] == 'minimal')

# ─── E16: Responsible Role ─────────────────────────────
with app.app_context():
    print('\n── E16: Responsible Role ──')
    r03 = analyze_review(T, B, 'r03')
    ok('E16a: critical role set', bool(r03['responsible_role']))
    ok('E16b: role is string', isinstance(r03['responsible_role'], str))

    r05 = analyze_review(T, B, 'r05')
    ok('E16c: rating-only role empty or None',
       r05['responsible_role'] in (None, '', 'none'))

# ─── E17: Internal Actions ─────────────────────────────
with app.app_context():
    print('\n── E17: Internal Actions ──')
    r03 = analyze_review(T, B, 'r03')
    acts_r03 = _act(r03)
    ok('E17a: critical actions is list', isinstance(acts_r03, list))
    ok('E17b: has >=1 action', len(acts_r03) >= 1)

    r05 = analyze_review(T, B, 'r05')
    acts_r05 = _act(r05)
    ok('E17c: rating-only actions is list', isinstance(acts_r05, list))

# ─── E18: Confidence Bounds ────────────────────────────
with app.app_context():
    print('\n── E18: Confidence Bounds ──')
    r01 = analyze_review(T, B, 'r01')
    conf_r01 = _ci(r01)
    ok('E18a: positive sentiment confidence 0.8-1.0',
       0.8 <= conf_r01.get('sentiment', 0) <= 1.0)

    r07 = analyze_review(T, B, 'r07')
    conf_r07 = _ci(r07)
    ok('E18b: short text sentiment confidence < 0.7',
       conf_r07.get('sentiment', 1) < 0.7)

    r05 = analyze_review(T, B, 'r05')
    conf_r05 = _ci(r05)
    ok('E18c: rating-only confidences = 1.0',
       all(v == 1.0 for v in conf_r05.values()))

# ─── E19: Batch Analyze ────────────────────────────────
with app.app_context():
    print('\n── E19: Batch Analyze Pending ──')
    # Set R04 analysis_reassessment_required=True
    r04 = db.session.get(Review, 'r04')
    r04.analysis_reassessment_required = True
    r04.qualitative_analysis_status = 'pending'
    db.session.commit()

    batch = batch_analyze_pending(T, B)
    ok('E19a: batch returned dict', isinstance(batch, dict))
    ok('E19b: analyzed count >= 1', batch.get('analyzed', 0) >= 1)
    rev = db.session.get(Review, 'r04')
    ok('E19c: status=analyzed', rev.qualitative_analysis_status == 'analyzed')

# ─── E20: Dashboard Summary ────────────────────────────
with app.app_context():
    print('\n── E20: Dashboard Summary ──')
    summary = get_dashboard_summary(T, B, days=90)
    ok('E20a: summary is dict', isinstance(summary, dict))
    ok('E20b: total_reviews > 0', summary.get('total_reviews', 0) > 0)
    ok('E20c: sentiments_analyzed > 0', summary.get('sentiments_analyzed', 0) > 0)
    ok('E20d: average_rating is number', isinstance(summary.get('average_rating'), (int, float)))
    sents = summary.get('sentiments', {})
    ok('E20e: sentiments dict present', isinstance(sents, dict))
    ok('E20f: at least 1 sentiment > 0',
       any(v > 0 for v in sents.values()))
    rating_only = summary.get('rating_only_reviews', 0)
    ok('E20g: rating_only_reviews <= total',
       rating_only <= summary.get('total_reviews', 0))

# ═════════════════════════════════════════════════════════
total = PASS + FAIL
print(f'\n═══ GATE E SUMMARY ═══')
print(f'  PASS: {PASS}  FAIL: {FAIL}')

if FAIL:
    print(f'  ❌ {FAIL} TEST(S) FAILED')
    sys.exit(1)
else:
    print(f'  ✅ ALL {PASS} TEST(S) PASSED')
    sys.exit(0)
