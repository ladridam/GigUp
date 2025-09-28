# routes/admin.py - Enhanced Admin routes
from flask import Blueprint, request, jsonify
from models.user import get_db
from routes.auth import admin_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@admin_required
def admin_get_users():
    db = get_db()
    users = db.execute('''SELECT id, name, email, phone, role, verified_email,
                            verified_phone, verified_social, is_approved, created_at
                            FROM users ORDER BY created_at DESC''').fetchall()
    
    return jsonify({'users': [dict(u) for u in users]}), 200

@admin_bp.route('/users/<int:user_id>/approve', methods=['PUT'])
@admin_required
def admin_approve_user(user_id):
    data = request.json
    approved = data.get('approved', True)
    
    db = get_db()
    try:
        db.execute('UPDATE users SET is_approved = ? WHERE id = ?', (approved, user_id))
        db.commit()
        
        status = 'approved' if approved else 'revoked'
        return jsonify({'message': f'User {status} successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to update user approval'}), 500

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def admin_stats():
    db = get_db()
    
    try:
        # Enhanced stats
        total_users = db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        verified_users = db.execute('SELECT COUNT(*) as count FROM users WHERE verified_email = 1').fetchone()['count']
        total_gigs = db.execute('SELECT COUNT(*) as count FROM gigs').fetchone()['count']
        active_gigs = db.execute('SELECT COUNT(*) as count FROM gigs WHERE status = "open"').fetchone()['count']
        completed_gigs = db.execute('SELECT COUNT(*) as count FROM gigs WHERE status = "completed"').fetchone()['count']
        total_contracts = db.execute('SELECT COUNT(*) as count FROM contracts').fetchone()['count']
        pending_applications = db.execute('SELECT COUNT(*) as count FROM applications WHERE status = "pending"').fetchone()['count']
        pending_approvals = db.execute('SELECT COUNT(*) as count FROM users WHERE is_approved = 0').fetchone()['count']
        
        # Recent activity
        recent_users = db.execute('SELECT COUNT(*) as count FROM users WHERE created_at > datetime("now", "-7 days")').fetchone()['count']
        recent_gigs = db.execute('SELECT COUNT(*) as count FROM gigs WHERE created_at > datetime("now", "-7 days")').fetchone()['count']
        
        stats = {
            'total_users': total_users,
            'verified_users': verified_users,
            'total_gigs': total_gigs,
            'active_gigs': active_gigs,
            'completed_gigs': completed_gigs,
            'total_contracts': total_contracts,
            'pending_applications': pending_applications,
            'pending_approvals': pending_approvals,
            'recent_users': recent_users,
            'recent_gigs': recent_gigs
        }
        
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch stats'}), 500