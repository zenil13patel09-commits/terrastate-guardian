"""
Authentication module for session-based auth
"""
from functools import wraps
from flask import session, redirect, url_for, flash
from models import Database, User


def init_auth(app):
    """Initialize authentication for Flask app"""
    app.secret_key = app.config.get('SECRET_KEY', 'dev-secret-key-change-in-production')


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def login_user(user_id: int, username: str):
    """Log in a user by setting session variables"""
    session['user_id'] = user_id
    session['username'] = username


def logout_user():
    """Log out the current user"""
    session.pop('user_id', None)
    session.pop('username', None)


def get_current_user():
    """Get current logged-in user info"""
    if 'user_id' in session:
        return {
            'id': session['user_id'],
            'username': session['username']
        }
    return None


def authenticate(username: str, password: str, db: Database) -> tuple[bool, dict]:
    """
    Authenticate user credentials
    
    Args:
        username: Username
        password: Password
        db: Database instance
        
    Returns:
        Tuple of (success, user_dict or error_message)
    """
    user_model = User(db)
    user = user_model.get_by_username(username)
    
    if not user:
        return False, {'error': 'Invalid username or password'}
    
    # Simple password check (in production, use proper hashing)
    if user['password'] != password:
        return False, {'error': 'Invalid username or password'}
    
    return True, user
