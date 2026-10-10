"""Create only NEW payment tables; does not touch existing user/medicine/order records."""
from app import app
from models import PaymentAttempt, db
with app.app_context():
    db.create_all()
    print("Payment table is ready. Existing users, medicines and orders were preserved.")
