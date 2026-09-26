"""
Authentication routes - Register, Login, Logout.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urljoin, urlsplit
from app import db, csrf
from app.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        errors = []
        
        if not name or len(name) < 2:
            errors.append('Name must be at least 2 characters.')
        
        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')
        
        if User.query.filter_by(email=email).first():
            errors.append('This email is already registered.')
        
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')

        # Create user
        try:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        # Validation
        if not email or not password:
            flash('Please enter email and password.', 'error')
            return render_template('auth/login.html')

        # Find user
        user = User.query.filter_by(email=email).first()

        if not user:
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html')

        # Check password
        if not user.check_password(password):
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html')

        # Log in
        login_user(user, remember=bool(remember))
        flash(f'Welcome back, {user.name}!', 'success')

        # Redirect to intended page or dashboard
        next_page = request.args.get('next')
        if next_page and _is_safe_redirect_target(request.host_url, next_page):
            return redirect(next_page)
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


def _is_safe_redirect_target(host_url, target):
    """Allow login redirects only to this application's host."""
    ref_url = urlsplit(host_url)
    test_url = urlsplit(urljoin(host_url, target))
    return test_url.scheme in {'http', 'https'} and ref_url.netloc == test_url.netloc


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """User logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page for updating details."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        if not name or len(name) < 2:
            flash('Name must be at least 2 characters.', 'error')
            return render_template('auth/profile.html')
        
        current_user.name = name
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')
