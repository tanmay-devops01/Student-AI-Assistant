"""
Reminder Service - Handles deadline reminders and notifications.
"""

import os
from datetime import datetime, timedelta
from typing import List
from flask import current_app
from app import db
from app.models.task import Task
from app.models.reminder import Reminder
from app.services.email_service import email_service


class ReminderService:
    """Service for checking and sending deadline reminders."""

    # Reminder thresholds in hours
    REMINDER_24H = 24
    REMINDER_1H = 1

    @classmethod
    def check_and_send_reminders(cls) -> int:
        """
        Check all pending tasks and send reminders for approaching/overdue deadlines.
        
        Returns:
            Number of reminders sent
        """
        now = datetime.utcnow()
        reminders_sent = 0

        # Get all pending and in-progress tasks with deadlines
        tasks = Task.query.filter(
            Task.user_id.isnot(None),
            Task.status.in_(['Pending', 'In Progress']),
            Task.deadline.isnot(None)
        ).all()

        for task in tasks:
            if task.is_overdue():
                # Send overdue notification if not already sent
                if not cls._has_reminder(task.id, 'overdue'):
                    cls._send_overdue_reminder(task)
                    reminders_sent += 1
            elif task.is_upcoming_soon(cls.REMINDER_1H):
                # Send 1-hour reminder if not already sent
                if not cls._has_reminder(task.id, 'upcoming_1h'):
                    cls._send_upcoming_reminder(task, cls.REMINDER_1H)
                    reminders_sent += 1
            elif task.is_upcoming_soon(cls.REMINDER_24H):
                # Send 24-hour reminder if not already sent
                if not cls._has_reminder(task.id, 'upcoming_24h'):
                    cls._send_upcoming_reminder(task, cls.REMINDER_24H)
                    reminders_sent += 1

        current_app.logger.info(f"Reminder check complete. Sent {reminders_sent} reminders.")
        return reminders_sent

    @classmethod
    def _has_reminder(cls, task_id: int, reminder_type: str) -> bool:
        """Check if a reminder of this type was already sent for this task."""
        return Reminder.query.filter_by(
            task_id=task_id,
            reminder_type=reminder_type
        ).first() is not None

    @classmethod
    def _send_overdue_reminder(cls, task: Task):
        """Send an overdue notification for a task."""
        reminder = Reminder(
            user_id=task.user_id,
            task_id=task.id,
            reminder_type='overdue'
        )
        db.session.add(reminder)
        db.session.commit()

        # Log the reminder
        current_app.logger.info(
            f"Overdue reminder: Task '{task.title}' (ID: {task.id}) "
            f"was due at {task.deadline}"
        )

        # Try to send email
        if email_service.is_configured():
            try:
                user = task.owner
                email_service.send_overdue_notification(
                    user_email=user.email,
                    user_name=user.name,
                    task_title=task.title,
                    deadline=task.deadline.strftime('%B %d, %Y %H:%M')
                )
                reminder.is_email_sent = True
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Failed to send overdue email: {str(e)}")

    @classmethod
    def _send_upcoming_reminder(cls, task: Task, hours: int):
        """Send an upcoming deadline reminder."""
        reminder_type = f'upcoming_{hours}h'
        reminder = Reminder(
            user_id=task.user_id,
            task_id=task.id,
            reminder_type=reminder_type
        )
        db.session.add(reminder)
        db.session.commit()

        # Calculate time remaining
        time_remaining = task.deadline - datetime.utcnow()
        hours_remaining = max(0, int(time_remaining.total_seconds() / 3600))

        current_app.logger.info(
            f"Upcoming reminder: Task '{task.title}' (ID: {task.id}) "
            f"due in {hours_remaining} hours"
        )

        # Try to send email
        if email_service.is_configured():
            try:
                user = task.owner
                email_service.send_deadline_reminder(
                    user_email=user.email,
                    user_name=user.name,
                    task_title=task.title,
                    deadline=task.deadline.strftime('%B %d, %Y %H:%M'),
                    hours_remaining=hours_remaining
                )
                reminder.is_email_sent = True
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Failed to send upcoming email: {str(e)}")

    @classmethod
    def create_reminder(cls, user_id: int, task_id: int, reminder_type: str) -> Reminder:
        """Create a manual reminder record."""
        reminder = Reminder(
            user_id=user_id,
            task_id=task_id,
            reminder_type=reminder_type
        )
        db.session.add(reminder)
        db.session.commit()
        return reminder

    @classmethod
    def get_user_reminders(cls, user_id: int, limit: int = 50) -> List[Reminder]:
        """Get recent reminders for a user."""
        return Reminder.query.filter_by(user_id=user_id)\
            .order_by(Reminder.sent_at.desc())\
            .limit(limit)\
            .all()
