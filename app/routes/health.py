"""Health check endpoint."""
from flask import Blueprint, jsonify, current_app
from app import db
from datetime import datetime, timezone

bp = Blueprint('health', __name__)


@bp.route('/health')
def health():
    """Health check — verifies DB connectivity and app status."""
    checks = {}
    healthy = True

    # DB check
    try:
        result = db.session.execute(db.text('SELECT 1'))
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {str(e)[:100]}'
        healthy = False

    status_code = 200 if healthy else 503
    return jsonify({
        'status': 'healthy' if healthy else 'unhealthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'app': current_app.config.get('APP_NAME', 'Google Reviews Monitoring'),
        'checks': checks,
    }), status_code
