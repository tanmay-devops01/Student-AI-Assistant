"""Subject model for organizing tasks by subject."""
from datetime import datetime
from app import db
from app.models.task import Task


class Subject(db.Model):
    """Subject model for categorizing and tracking academic subjects."""
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(7), default='#0d6efd')  # Bootstrap primary blue
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tasks = db.relationship('Task', backref='subject', lazy=True)

    def get_stats(self):
        """Calculate subject statistics."""
        total = Task.query.filter_by(subject_id=self.id).count()
        completed = Task.query.filter_by(subject_id=self.id, status='Completed').count()
        pending = total - completed
        percentage = (completed / total * 100) if total > 0 else 0

        return {
            'total_tasks': total,
            'completed_tasks': completed,
            'pending_tasks': pending,
            'completion_percentage': percentage
        }

    def __repr__(self):
        return f'<Subject {self.name}>'
