"""
Reports routes - Weekly and custom date range reports.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.models.task import Task
from app.models.subject import Subject
from app.services.summary_service import SummaryService
from app.services.ai_service import ai_service

reports_bp = Blueprint('reports', __name__, url_prefix='/reports', static_folder=None, static_url_path=None)


@reports_bp.route('/')
@login_required
def index():
    """Weekly report page (default)."""
    return render_report('week')


@reports_bp.route('/week')
@login_required
def weekly_report():
    """Show weekly report."""
    return render_report('week')


@reports_bp.route('/month')
@login_required
def monthly_report():
    """Show monthly report."""
    return render_report('month')


@reports_bp.route('/custom', methods=['GET', 'POST'])
@login_required
def custom_report():
    """Show custom date range report."""
    if request.method == 'POST':
        start_date_str = request.form.get('start_date', '')
        end_date_str = request.form.get('end_date', '')
        
        if not start_date_str or not end_date_str:
            flash('Please select both start and end dates.', 'error')
            return render_template(
                'reports/custom.html',
                now=datetime.utcnow(),
                default_start=(datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)).strftime('%Y-%m-%d'),
                default_end=datetime.utcnow().strftime('%Y-%m-%d')
            )
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            if end_date < start_date:
                flash('End date must be after start date.', 'error')
                return render_template(
                    'reports/custom.html',
                    now=datetime.utcnow(),
                    default_start=(datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)).strftime('%Y-%m-%d'),
                    default_end=datetime.utcnow().strftime('%Y-%m-%d')
                )
        except ValueError:
            flash('Invalid date format.', 'error')
            return render_template(
                'reports/custom.html',
                now=datetime.utcnow(),
                default_start=(datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)).strftime('%Y-%m-%d'),
                default_end=datetime.utcnow().strftime('%Y-%m-%d')
            )
        
        return render_custom_report(start_date, end_date)
    
    return render_template(
        'reports/custom.html',
        now=datetime.utcnow(),
        default_start=(datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)).strftime('%Y-%m-%d'),
        default_end=datetime.utcnow().strftime('%Y-%m-%d')
    )


def render_report(period: str):
    """Render report for a given period."""
    now = datetime.utcnow()
    current_user_id = current_user.id
    
    if period == 'week':
        start_date = now - timedelta(days=now.weekday())  # Monday
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
        period_name = f"Week {now.isocalendar()[1]}"
    elif period == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end_date = now.replace(year=now.year + 1, month=1, day=1)
        else:
            end_date = now.replace(month=now.month + 1, day=1)
        period_name = now.strftime('%B %Y')
    else:
        start_date = now - timedelta(days=7)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
        period_name = 'Last 7 Days'
    
    # Get tasks in period
    tasks_created = Task.query.filter(
        Task.user_id == current_user_id,
        Task.created_at >= start_date,
        Task.created_at < end_date
    ).all()
    
    tasks_completed = Task.query.filter(
        Task.user_id == current_user_id,
        Task.status == 'Completed',
        Task.completed_at >= start_date,
        Task.completed_at < end_date
    ).all()
    
    tasks_overdue = Task.query.filter(
        Task.user_id == current_user_id,
        Task.status.in_(['Pending', 'In Progress']),
        Task.deadline.isnot(None),
        Task.deadline < now
    ).all()
    
    # Calculate statistics
    total_tasks = Task.query.filter_by(user_id=current_user_id).count()
    completed_tasks = Task.query.filter_by(
        user_id=current_user_id,
        status='Completed'
    ).count()
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Subject-wise progress
    subjects = Subject.query.filter_by(user_id=current_user_id).all()
    subject_progress = []
    for subject in subjects:
        total = Task.query.filter_by(subject_id=subject.id).count()
        completed = Task.query.filter_by(subject_id=subject.id, status='Completed').count()
        percentage = (completed / total * 100) if total > 0 else 0
        subject_progress.append({
            'name': subject.name,
            'color': subject.color,
            'total': total,
            'completed': completed,
            'percentage': percentage
        })
    
    # Daily breakdown for chart
    daily_data = []
    if period == 'week':
        days = 7
    elif period == 'month':
        days = (end_date - start_date).days
    else:
        days = (end_date - start_date).days + 1
    
    for i in range(days):
        day_start = end_date - timedelta(days=days - i)
        day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        if day_start >= start_date:
            created = Task.query.filter(
                Task.user_id == current_user_id,
                Task.created_at >= day_start,
                Task.created_at < day_end
            ).count()
            
            completed = Task.query.filter(
                Task.user_id == current_user_id,
                Task.status == 'Completed',
                Task.completed_at >= day_start,
                Task.completed_at < day_end
            ).count()
            
            day_name = day_start.strftime('%a %d')
            daily_data.append({
                'day': day_name,
                'created': created,
                'completed': completed
            })
    
    # AI-generated insights if available
    insights = None
    recommendations = []
    if ai_service.is_available() and tasks_created:
        # Generate weekly insights
        try:
            context = f"""Period: {period_name}
Tasks created: {len(tasks_created)}
Tasks completed: {len(tasks_completed)}
Overdue tasks: {len(tasks_overdue)}
Completion rate: {completion_rate:.1f}%
"""
            for subject in subject_progress[:5]:
                context += f"\n{subject['name']}: {subject['completed']}/{subject['total']} ({subject['percentage']:.1f}%)"
            
            prompt = f"""Based on this study data, provide 3-5 actionable insights and recommendations:

{context}

Respond with JSON:
{{
  "insights": ["Insight 1", "Insight 2"],
  "recommendations": ["Recommendation 1", "Recommendation 2", "Recommendation 3"]
}}"""
            
            # This would use ai_service if fully implemented
            # For now, provide basic insights
            insights = [
                f"Completed {len(tasks_completed)} tasks this {period}",
                f"Created {len(tasks_created)} new tasks",
                f"Have {len(tasks_overdue)} overdue tasks requiring attention"
            ]
            recommendations = [
                "Focus on completing overdue tasks first",
                "Maintain your current productivity pace",
                "Review subjects with lower completion rates"
            ]
        except Exception:
            pass
    
    return render_template(
        'reports/index.html',
        period=period,
        period_name=period_name,
        start_date=start_date,
        end_date=end_date,
        tasks_created_count=len(tasks_created),
        tasks_completed_count=len(tasks_completed),
        tasks_overdue_count=len(tasks_overdue),
        completion_rate=completion_rate,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        subject_progress=subject_progress,
        daily_data=daily_data,
        insights=insights,
        recommendations=recommendations,
        ai_available=ai_service.is_available()
    )


def render_custom_report(start_date: datetime, end_date: datetime):
    """Render report for a custom date range."""
    current_user_id = current_user.id
    end_exclusive = end_date + timedelta(days=1)
    period_name = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    
    # Get tasks in range
    tasks_created = Task.query.filter(
        Task.user_id == current_user_id,
        Task.created_at >= start_date,
        Task.created_at < end_exclusive
    ).all()
    
    tasks_completed = Task.query.filter(
        Task.user_id == current_user_id,
        Task.status == 'Completed',
        Task.completed_at >= start_date,
        Task.completed_at < end_exclusive
    ).all()
    
    tasks_overdue = Task.query.filter(
        Task.user_id == current_user_id,
        Task.status.in_(['Pending', 'In Progress']),
        Task.deadline.isnot(None),
        Task.deadline < datetime.utcnow()
    ).all()
    
    # Subject-wise progress
    subjects = Subject.query.filter_by(user_id=current_user_id).all()
    subject_progress = []
    for subject in subjects:
        total = Task.query.filter_by(subject_id=subject.id).count()
        completed = Task.query.filter_by(subject_id=subject.id, status='Completed').count()
        percentage = (completed / total * 100) if total > 0 else 0
        subject_progress.append({
            'name': subject.name,
            'color': subject.color,
            'total': total,
            'completed': completed,
            'percentage': percentage
        })
    
    # Total statistics
    total_tasks = Task.query.filter_by(user_id=current_user_id).count()
    completed_tasks = Task.query.filter_by(
        user_id=current_user_id,
        status='Completed'
    ).count()
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return render_template(
        'reports/index.html',
        period='custom',
        period_name=period_name,
        start_date=start_date,
        end_date=end_date,
        tasks_created_count=len(tasks_created),
        tasks_completed_count=len(tasks_completed),
        tasks_overdue_count=len(tasks_overdue),
        completion_rate=completion_rate,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        subject_progress=subject_progress,
        daily_data=[],
        insights=None,
        recommendations=[],
        ai_available=ai_service.is_available(),
        is_custom=True
    )
