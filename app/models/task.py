"""Task model for managing assignments and to-dos."""
from datetime import datetime
from app import db


class Task(db.Model):
    """Task model for managing student assignments and tasks."""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default='Medium')  # Low, Medium, High
    status = db.Column(db.String(20), default='Pending')  # Pending, In Progress, Completed
    deadline = db.Column(db.DateTime, nullable=True)
    estimated_minutes = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    reminders = db.relationship('Reminder', backref='task', lazy=True, cascade='all, delete-orphan')

    def mark_complete(self):
        """Mark the task as completed."""
        self.status = 'Completed'
        self.completed_at = datetime.utcnow()

    def mark_incomplete(self):
        """Mark the task as incomplete."""
        self.status = 'Pending'
        self.completed_at = None

    def is_overdue(self):
        """Check if the task is overdue."""
        if not self.deadline or self.status == 'Completed':
            return False
        return datetime.utcnow() > self.deadline

    def is_upcoming_soon(self, hours=24):
        """Check if deadline is approaching within specified hours."""
        if not self.deadline or self.status == 'Completed':
            return False
        from datetime import timedelta
        return datetime.utcnow() + timedelta(hours=hours) >= self.deadline

    def to_dict(self):
        """Convert task to dictionary for API responses."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'estimated_minutes': self.estimated_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else None
        }

    def __repr__(self):
        return f'<Task {self.title}>'
