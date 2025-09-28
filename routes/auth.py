# routes/auth.py - Authentication routes
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from models.user import get_db
from utils.validation import validate_email, validate_phone, validate_password
import secrets
from datetime import datetime, timedelta
from functools import wraps

auth_bp = Blueprint('auth', __name__)

# Authentication decorators
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        db = get_db()
        user = db.execute('SELECT id, is_approved FROM users WHERE id = ?', 
                        (session['user_id'],)).fetchone()
        
        if not user:
            session.pop('user_id', None)
            return jsonify({'error': 'User account not found'}), 404
            
        if not user['is_approved']:
            return jsonify({'error': 'Account pending approval'}), 403
            
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        db = get_db()
        user = db.execute('SELECT role FROM users WHERE id = ?', 
                        (session['user_id'],)).fetchone()
        
        if not user or user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
            
        return f(*args, **kwargs)
    return decorated_function

# Helper functions
def generate_verification_code(user_id, verification_type):
    """Generate and store verification code"""
    db = get_db()
    code = secrets.token_urlsafe(8)
    expires_at = datetime.now() + timedelta(hours=24)
    
    # Invalidate any existing codes for this type
    db.execute('UPDATE verification_codes SET used = 1 WHERE user_id = ? AND type = ? AND used = 0',
               (user_id, verification_type))
    
    # Insert new code
    db.execute('''INSERT INTO verification_codes (user_id, code, type, expires_at)
                  VALUES (?, ?, ?, ?)''',
               (user_id, code, verification_type, expires_at))
    db.commit()
    
    return code

def validate_verification_code(user_id, verification_type, code):
    """Validate verification code"""
    db = get_db()
    verification = db.execute('''SELECT * FROM verification_codes 
                               WHERE user_id = ? AND type = ? AND code = ? 
                               AND used = 0 AND expires_at > ?''',
                             (user_id, verification_type, code, datetime.now())).fetchone()
    return verification is not None

def mark_verification_code_used(verification_id):
    """Mark verification code as used"""
    db = get_db()
    db.execute('UPDATE verification_codes SET used = 1 WHERE id = ?', (verification_id,))
    db.commit()

# Authentication endpoints
@auth_bp.route('/signup', methods=['POST'])
def signup():
    """Register a new user"""
    data = request.json
    
    # Validate required fields
    required = ['name', 'email', 'phone', 'password']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Enhanced validation
    if not validate_email(data['email']):
        return jsonify({'error': 'Invalid email format'}), 400
    
    if not validate_phone(data['phone']):
        return jsonify({'error': 'Invalid phone number'}), 400
    
    if not validate_password(data['password']):
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Hash password
    password_hash = generate_password_hash(data['password'])
    db = get_db()
    
    try:
        c = db.cursor()
        c.execute('''INSERT INTO users (name, email, phone, password_hash) 
                     VALUES (?, ?, ?, ?)''',
                  (data['name'], data['email'], data['phone'], password_hash))
        user_id = c.lastrowid
        
        # Generate email verification code
        verification_code = generate_verification_code(user_id, 'email')
        
        db.commit()
        
        return jsonify({
            'message': 'User created successfully. Please wait for admin approval.',
            'user_id': user_id,
            'verification_code': verification_code,  # Remove in production
            'note': 'In production, this code would be sent via email'
        }), 201
        
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'Email already exists'}), 400
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and create session"""
    data = request.json
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ?', (data['email'],)).fetchone()
    
    if not user or not check_password_hash(user['password_hash'], data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user['is_approved']:
        return jsonify({'error': 'Account pending admin approval'}), 403
    
    # Create session
    session['user_id'] = user['id']
    session['user_role'] = user['role']
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'verified_email': bool(user['verified_email']),
            'verified_phone': bool(user['verified_phone']),
            'verified_social': bool(user['verified_social']),
            'is_approved': bool(user['is_approved']),
            'skills': user['skills'],
            'bio': user['bio'],
            'rating': user['rating'],
            'total_ratings': user['total_ratings']
        }
    }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user and clear session"""
    session.pop('user_id', None)
    session.pop('user_role', None)
    return jsonify({'message': 'Logged out successfully'}), 200

@auth_bp.route('/me', methods=['GET'])
@auth_required
def get_current_user():
    """Get current user profile"""
    db = get_db()
    user = db.execute('''SELECT id, name, email, phone, role, skills, bio, rating, 
                       total_ratings, verified_email, verified_phone, 
                       verified_social, is_approved, created_at 
                       FROM users WHERE id = ?''', (session['user_id'],)).fetchone()
    
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({'user': dict(user)}), 200

# Profile management endpoints
@auth_bp.route('/profile', methods=['PUT'])
@auth_required
def update_profile():
    """Update user profile"""
    data = request.json
    user_id = session['user_id']
    
    allowed_fields = ['name', 'phone', 'skills', 'bio']
    update_fields = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_fields:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    # Validate phone if being updated
    if 'phone' in update_fields and not validate_phone(update_fields['phone']):
        return jsonify({'error': 'Invalid phone number'}), 400
    
    db = get_db()
    try:
        set_clause = ', '.join([f'{k} = ?' for k in update_fields.keys()])
        values = list(update_fields.values()) + [user_id]
        
        db.execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
        db.commit()
        
        return jsonify({'message': 'Profile updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Profile update failed'}), 500

@auth_bp.route('/profile/password', methods=['PUT'])
@auth_required
def change_password():
    """Change user password"""
    data = request.json
    user_id = session['user_id']
    
    required = ['current_password', 'new_password']
    if not all(k in data for k in required):
        return jsonify({'error': 'Current password and new password required'}), 400
    
    if not validate_password(data['new_password']):
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    
    db = get_db()
    user = db.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user or not check_password_hash(user['password_hash'], data['current_password']):
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    try:
        new_password_hash = generate_password_hash(data['new_password'])
        db.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                   (new_password_hash, user_id))
        db.commit()
        
        return jsonify({'message': 'Password updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Password update failed'}), 500

# Verification endpoints
@auth_bp.route('/verify/email/send', methods=['POST'])
@auth_required
def send_email_verification():
    """Send email verification code"""
    user_id = session['user_id']
    
    db = get_db()
    user = db.execute('SELECT verified_email FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if user and user['verified_email']:
        return jsonify({'error': 'Email already verified'}), 400
    
    try:
        verification_code = generate_verification_code(user_id, 'email')
        
        # In production, send actual email here
        # For MVP, return the code
        return jsonify({
            'message': 'Verification code sent successfully',
            'verification_code': verification_code,  # Remove in production
            'note': 'In production, this would be sent via email'
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to send verification code'}), 500

@auth_bp.route('/verify/phone/send', methods=['POST'])
@auth_required
def send_phone_verification():
    """Send phone verification code"""
    user_id = session['user_id']
    
    db = get_db()
    user = db.execute('SELECT verified_phone FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if user and user['verified_phone']:
        return jsonify({'error': 'Phone already verified'}), 400
    
    try:
        verification_code = generate_verification_code(user_id, 'phone')
        
        # In production, send actual SMS here
        # For MVP, return the code
        return jsonify({
            'message': 'Verification code sent successfully',
            'verification_code': verification_code,  # Remove in production
            'note': 'In production, this would be sent via SMS'
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to send verification code'}), 500

@auth_bp.route('/verify/email', methods=['POST'])
@auth_required
def verify_email():
    """Verify email with code"""
    return verify_account('email')

@auth_bp.route('/verify/phone', methods=['POST'])
@auth_required
def verify_phone():
    """Verify phone with code"""
    return verify_account('phone')

def verify_account(verification_type):
    """Common verification function for email and phone"""
    data = request.json
    user_id = session['user_id']
    code = data.get('code')
    
    if verification_type not in ['email', 'phone']:
        return jsonify({'error': 'Invalid verification type'}), 400
    
    if not code:
        return jsonify({'error': 'Verification code required'}), 400
    
    db = get_db()
    
    try:
        # Check verification code
        verification = db.execute('''SELECT * FROM verification_codes 
                                   WHERE user_id = ? AND type = ? AND code = ? 
                                   AND used = 0 AND expires_at > ?''',
                                 (user_id, verification_type, code, datetime.now())).fetchone()
        
        if not verification:
            return jsonify({'error': 'Invalid or expired verification code'}), 400
        
        # Mark code as used
        mark_verification_code_used(verification['id'])
        
        # Update user verification status
        field = f'verified_{verification_type}'
        db.execute(f'UPDATE users SET {field} = 1 WHERE id = ?', (user_id,))
        db.commit()
        
        return jsonify({'message': f'{verification_type.capitalize()} verified successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Verification failed'}), 500

# Password reset endpoints
@auth_bp.route('/password/reset/request', methods=['POST'])
def request_password_reset():
    """Request password reset"""
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    db = get_db()
    user = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    
    if user:
        # Generate reset token (in production, this would be a secure token)
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)
        
        # Store reset token (in production, use a separate table for reset tokens)
        # For MVP, we'll use the verification_codes table
        db.execute('''INSERT INTO verification_codes (user_id, code, type, expires_at)
                      VALUES (?, ?, 'password_reset', ?)''',
                   (user['id'], reset_token, expires_at))
        db.commit()
        
        # In production, send email with reset link
        # For MVP, return the token
        return jsonify({
            'message': 'Password reset instructions sent',
            'reset_token': reset_token,  # Remove in production
            'note': 'In production, this would be sent via email'
        }), 200
    
    # Always return success to prevent email enumeration
    return jsonify({'message': 'If the email exists, reset instructions have been sent'}), 200

@auth_bp.route('/password/reset', methods=['POST'])
def reset_password():
    """Reset password with token"""
    data = request.json
    token = data.get('token')
    new_password = data.get('new_password')
    
    if not token or not new_password:
        return jsonify({'error': 'Token and new password required'}), 400
    
    if not validate_password(new_password):
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    db = get_db()
    
    try:
        # Verify reset token
        verification = db.execute('''SELECT * FROM verification_codes 
                                   WHERE code = ? AND type = 'password_reset' 
                                   AND used = 0 AND expires_at > ?''',
                                 (token, datetime.now())).fetchone()
        
        if not verification:
            return jsonify({'error': 'Invalid or expired reset token'}), 400
        
        # Update password
        new_password_hash = generate_password_hash(new_password)
        db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                   (new_password_hash, verification['user_id']))
        
        # Mark token as used
        mark_verification_code_used(verification['id'])
        
        db.commit()
        
        return jsonify({'message': 'Password reset successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Password reset failed'}), 500

# Session check endpoint
@auth_bp.route('/session', methods=['GET'])
def check_session():
    """Check if user has valid session"""
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 200
    
    db = get_db()
    user = db.execute('SELECT id, is_approved FROM users WHERE id = ?', 
                     (session['user_id'],)).fetchone()
    
    if not user or not user['is_approved']:
        session.clear()
        return jsonify({'authenticated': False}), 200
    
    return jsonify({'authenticated': True}), 200