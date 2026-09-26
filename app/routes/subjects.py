"""
Subject Management routes - CRUD operations for subjects.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
import re
from app import db
from app.models.subject import Subject

subjects_bp = Blueprint('subjects', __name__, url_prefix='/subjects', static_folder=None, static_url_path=None)


@subjects_bp.route('/')
@login_required
def index():
    """List all subjects."""
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    
    # Get statistics for each subject
    subject_stats = []
    for subject in subjects:
        stats = subject.get_stats()
        subject_stats.append({
            'subject': subject,
            'stats': stats
        })
    
    total_tasks = sum(s['stats']['total_tasks'] for s in subject_stats)
    total_completed = sum(s['stats']['completed_tasks'] for s in subject_stats)
    
    return render_template(
        'subjects/index.html',
        subjects=subjects,
        subject_stats=subject_stats,
        total_tasks=total_tasks,
        total_completed=total_completed
    )


@subjects_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new subject."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        color = request.form.get('color', '#0d6efd')

        # Validation
        if not name:
            flash('Subject name is required.', 'error')
            return render_template('subjects/create.html')

        if len(name) > 100:
            flash('Subject name is too long.', 'error')
            return render_template('subjects/create.html')

        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            color = '#0d6efd'

        # Check for duplicate
        existing = Subject.query.filter_by(
            user_id=current_user.id,
            name=name
        ).first()
        
        if existing:
            flash('A subject with this name already exists.', 'error')
            return render_template('subjects/create.html')

        # Create subject
        try:
            subject = Subject(
                user_id=current_user.id,
                name=name,
                description=description,
                color=color
            )
            db.session.add(subject)
            db.session.commit()
            flash('Subject created successfully!', 'success')
            return redirect(url_for('subjects.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create subject: {str(e)}', 'error')
            return render_template('subjects/create.html')

    return render_template('subjects/create.html')


@subjects_bp.route('/<int:subject_id>')
@login_required
def view(subject_id):
    """View a specific subject with its tasks."""
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    stats = subject.get_stats()
    
    # Get tasks for this subject
    from app.models.task import Task
    tasks = Task.query.filter_by(subject_id=subject_id).order_by(Task.created_at.desc()).all()
    
    return render_template('subjects/view.html', subject=subject, stats=stats, tasks=tasks)


@subjects_bp.route('/<int:subject_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(subject_id):
    """Edit a subject."""
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        color = request.form.get('color', '#0d6efd')

        # Validation
        if not name:
            flash('Subject name is required.', 'error')
            return render_template('subjects/edit.html', subject=subject)
        if len(name) > 100:
            flash('Subject name is too long.', 'error')
            return render_template('subjects/edit.html', subject=subject)
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            color = '#0d6efd'

        # Check for duplicate (excluding current)
        existing = Subject.query.filter(
            Subject.user_id == current_user.id,
            Subject.name == name,
            Subject.id != subject_id
        ).first()
        
        if existing:
            flash('A subject with this name already exists.', 'error')
            return render_template('subjects/edit.html', subject=subject)

        # Update subject
        subject.name = name
        subject.description = description
        subject.color = color

        try:
            db.session.commit()
            flash('Subject updated successfully!', 'success')
            return redirect(url_for('subjects.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update subject: {str(e)}', 'error')
            return render_template('subjects/edit.html', subject=subject)

    return render_template('subjects/edit.html', subject=subject)


@subjects_bp.route('/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete(subject_id):
    """Delete a subject."""
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()

    try:
        db.session.delete(subject)
        db.session.commit()
        flash('Subject deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete subject: {str(e)}', 'error')

    return redirect(url_for('subjects.index'))
