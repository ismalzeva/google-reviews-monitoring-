"""Entry point — Google Reviews Monitoring & Intelligence."""
import os
from app import create_app, db

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('APP_PORT', 8083))
    app.run(host='0.0.0.0', port=port, debug=False)
