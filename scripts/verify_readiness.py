"""Verify readiness endpoint with new pilot data"""
import sys
sys.path.insert(0, '/home/ubuntu/google-reviews-monitoring')
from app import create_app

app = create_app()
with app.test_client() as client:
    resp = client.get('/production/readiness')
    data = resp.get_json()
    
    print('=== Readiness Check with Pilot Data ===')
    print(f'Overall: {data["overall"]["status"]}')
    print(f'Pilot mode: {data["pilot"]["pilot_mode"]}')
    print(f'Max outlets: {data["pilot"]["max_outlets"]}')
    print(f'Whitelist: {data["pilot"]["outlet_whitelist"]}')
    print(f'Harjamukti excluded: {data["pilot"]["harjamukti_excluded"]}')
    print(f'Auto-reply: {data["security"]["auto_reply_enabled"]}')
    print(f'Reply enabled: {data["security"]["reply_enabled_globally"]}')
    print(f'Rollback: {data["security"]["rollback"]}')
