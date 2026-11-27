from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db
from app.models import User

def run_seed():
    app = create_app()
    with app.app_context():
        db.create_all()
        
        # 1. Seed Users (Admin & Viewer)
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@internal.enterprise.com',
                role='Admin',
                is_active_account=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=60)
            )
            admin_user.set_password('Admin@12345')
            db.session.add(admin_user)
        else:
            admin_user = User.query.filter_by(username='admin').first()
            admin_user.set_password('Admin@12345')
            
        if not User.query.filter_by(username='viewer').first():
            viewer_user = User(
                username='viewer',
                email='viewer@internal.enterprise.com',
                role='Viewer',
                is_active_account=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=45)
            )
            viewer_user.set_password('Viewer@12345')
            db.session.add(viewer_user)
        else:
            viewer_user = User.query.filter_by(username='viewer').first()
            viewer_user.set_password('Viewer@12345')

        db.session.commit()
        print("Seeded default admin and viewer users (empty keys & applications).")

if __name__ == '__main__':
    run_seed()
    print("Database seeding completed successfully!")
