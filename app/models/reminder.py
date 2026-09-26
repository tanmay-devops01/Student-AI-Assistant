"""Reminder model for tracking automated notifications."""
from datetime import datetime
from app import db


class Reminder(db.Model):
    """Reminder model for tracking sent notifications."""
    __tablename__ = 'reminders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    reminder_type = db.Column(db.String(50), nullable=False)  # upcoming_24h, upcoming_1h, overdue
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_email_sent = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Reminder {self.reminder_type} for task {self.task_id}>'
