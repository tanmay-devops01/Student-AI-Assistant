"""
Summary Service - Generates and sends daily/weekly summaries.
"""

from datetime import datetime, timedelta
from typing import List
from flask import current_app
from app.models.task import Task
from app.models.user import User
from app.services.email_service import email_service
from app.services.ai_service import ai_service


class SummaryService:
    """Service for generating and sending study summaries."""

    @classmethod
    def send_daily_summaries(cls):
        """Send daily study summaries to all users."""
        users = User.query.all()
        
        for user in users:
            try:
                cls._send_user_daily_summary(user)
            except Exception as e:
                current_app.logger.error(
                    f"Failed to send daily summary to {user.email}: {str(e)}"
                )

    @classmethod
    def _send_user_daily_summary(cls, user: User):
        """Send daily summary to a specific user."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Get tasks due today.
        tasks_today = Task.query.filter(
            Task.user_id == user.id,
            Task.deadline >= today_start,
            Task.deadline < today_end
        ).all()

        # Get completed today
        completed_today = Task.query.filter(
            Task.user_id == user.id,
            Task.status == 'Completed',
            Task.completed_at >= today_start,
            Task.completed_at < today_end
        ).all()

        # Get upcoming deadlines (next 3 days)
        upcoming_deadlines = Task.query.filter(
            Task.user_id == user.id,
            Task.status.in_(['Pending', 'In Progress']),
            Task.deadline.isnot(None),
            Task.deadline > now,
            Task.deadline <= now + timedelta(days=3)
        ).order_by(Task.deadline).limit(5).all()

        # Format data for summary
        tasks_data = [{
            'title': t.title,
            'status': t.status,
            'deadline': t.deadline.strftime('%Y-%m-%d') if t.deadline else None
        } for t in tasks_today]

        deadlines_data = [{
            'title': t.title,
            'deadline': t.deadline.strftime('%Y-%m-%d') if t.deadline else None
        } for t in upcoming_deadlines]

        # Generate AI summary if available
        summary_text = f"You have {len(tasks_today)} tasks scheduled for today."
        recommendations = []

        if ai_service.is_available():
            ai_result = ai_service.generate_daily_summary(tasks_data, len(completed_today))
            if ai_result.get('success'):
                summary_text = ai_result.get('summary', summary_text)
                recommendations = ai_result.get('recommendations', [])

        # Send email if configured
        if email_service.is_configured():
            email_service.send_daily_summary(
                user_email=user.email,
                user_name=user.name,
                summary=summary_text,
                tasks_today=tasks_data,
                completed_today=len(completed_today),
                upcoming_deadlines=deadlines_data
            )

        current_app.logger.info(
            f"Daily summary sent to {user.email}"
        )

    @classmethod
    def send_weekly_reports(cls):
        """Send weekly progress reports to all users."""
        users = User.query.all()
        
        for user in users:
            try:
                cls._send_user_weekly_report(user)
            except Exception as e:
                current_app.logger.error(
                    f"Failed to send weekly report to {user.email}: {str(e)}"
                )

    @classmethod
    def _send_user_weekly_report(cls, user: User):
        """Send weekly report to a specific user."""
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())  # Monday
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        # Get weekly statistics
        tasks_created = Task.query.filter(
            Task.user_id == user.id,
            Task.created_at >= week_start,
            Task.created_at < week_end
        ).count()

        tasks_completed = Task.query.filter(
            Task.user_id == user.id,
            Task.status == 'Completed',
            Task.completed_at >= week_start,
            Task.completed_at < week_end
        ).count()

        # Get all tasks for completion rate
        all_tasks = Task.query.filter_by(user_id=user.id).all()
        total_tasks = len(all_tasks)
        completed_tasks = sum(1 for t in all_tasks if t.status == 'Completed')
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        report_data = {
            'completion_percentage': completion_rate,
            'completed_this_week': tasks_completed,
            'created_this_week': tasks_created,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks
        }

        # Send email if configured
        if email_service.is_configured():
            email_service.send_weekly_report(
                user_email=user.email,
                user_name=user.name,
                report_data=report_data
            )

        current_app.logger.info(
            f"Weekly report sent to {user.email}"
        )

    @classmethod
    def get_weekly_stats(cls, user_id: int) -> dict:
        """Get weekly statistics for a user."""
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        tasks_created = Task.query.filter(
            Task.user_id == user_id,
            Task.created_at >= week_start,
            Task.created_at < week_end
        ).count()

        tasks_completed = Task.query.filter(
            Task.user_id == user_id,
            Task.status == 'Completed',
            Task.completed_at >= week_start,
            Task.completed_at < week_end
        ).count()

        tasks_overdue = Task.query.filter(
            Task.user_id == user_id,
            Task.status.in_(['Pending', 'In Progress']),
            Task.deadline.isnot(None),
            Task.deadline < now
        ).count()

        all_tasks = Task.query.filter_by(user_id=user_id).all()
        total_tasks = len(all_tasks)
        completed_tasks = sum(1 for t in all_tasks if t.status == 'Completed')
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        # Get daily breakdown for chart
        daily_stats = []
        for i in range(7):
            day_start = now - timedelta(days=6-i)
            day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            created = Task.query.filter(
                Task.user_id == user_id,
                Task.created_at >= day_start,
                Task.created_at < day_end
            ).count()

            completed = Task.query.filter(
                Task.user_id == user_id,
                Task.status == 'Completed',
                Task.completed_at >= day_start,
                Task.completed_at < day_end
            ).count()

            day_name = day_start.strftime('%a')
            daily_stats.append({
                'day': day_name,
                'created': created,
                'completed': completed
            })

        return {
            'completed_this_week': tasks_completed,
            'created_this_week': tasks_created,
            'overdue_tasks': tasks_overdue,
            'completion_percentage': completion_rate,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'daily_stats': daily_stats
        }
