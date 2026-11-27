import os
from app import create_app
from app.extensions import db

app = create_app(os.getenv('FLASK_CONFIG', 'default'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        from app.models import User
        if not User.query.first():
            from seed import run_
            
            seed
            run_seed()
    app.run(host='0.0.0.0', port=5001, debug=True)
