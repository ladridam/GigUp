# routes/gigs.py - Gigs routes
from flask import Blueprint, request, jsonify, session
from models.user import get_db
from utils.location import haversine_distance, calculate_match_score
from utils.validation import validate_coordinates
import secrets
from datetime import datetime, timedelta
from functools import wraps

gigs_bp = Blueprint('gigs', __name__)

# Import auth decorators
from routes.auth import auth_required, admin_required

@gigs_bp.route('/gigs', methods=['POST'])
@auth_required
def create_gig():
    data = request.json
    provider_id = session['user_id']
    
    required = ['title', 'category', 'date_time', 'pay', 'location_lat', 'location_lng']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Validate numeric fields
    try:
        pay = float(data['pay'])
        lat = float(data['location_lat'])
        lng = float(data['location_lng'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numeric values'}), 400
    
    if not validate_coordinates(lat, lng):
        return jsonify({'error': 'Invalid coordinates'}), 400
    
    db = get_db()
    try:
        c = db.cursor()
        c.execute('''INSERT INTO gigs (provider_id, title, category, skills_required,
                     description, date_time, duration, pay, location_lat, location_lng,
                     location_address) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (provider_id, data['title'], data['category'], 
                   data.get('skills_required'), data.get('description'),
                   data['date_time'], data.get('duration'), pay,
                   lat, lng, data.get('location_address')))
        gig_id = c.lastrowid
        db.commit()
        
        return jsonify({'message': 'Gig created successfully', 'gig_id': gig_id}), 201
    except Exception as e:
        print(f"Error creating gig: {str(e)}")
        return jsonify({'error': 'Failed to create gig'}), 500

@gigs_bp.route('/gigs', methods=['GET'])
def get_gigs():
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    max_distance = request.args.get('max_distance', 35, type=float)
    category = request.args.get('category')
    user_id = request.args.get('user_id', type=int)
    
    db = get_db()
    
    if user_id:
        # Get gigs for specific user
        query = '''SELECT g.*, u.name as provider_name, u.rating as provider_rating
                   FROM gigs g JOIN users u ON g.provider_id = u.id 
                   WHERE g.provider_id = ? ORDER BY g.created_at DESC'''
        gigs = db.execute(query, (user_id,)).fetchall()
        result = [dict(gig) for gig in gigs]
    else:
        # Get all gigs with filters
        query = '''SELECT g.*, u.name as provider_name, u.rating as provider_rating
                   FROM gigs g JOIN users u ON g.provider_id = u.id 
                   WHERE g.status = 'open' '''
        params = []
        
        if category:
            query += ' AND g.category = ?'
            params.append(category)
        
        gigs = db.execute(query, params).fetchall()
        
        result = []
        for gig in gigs:
            gig_dict = dict(gig)
            
            # Calculate distance if user location provided
            if lat and lng:
                distance = haversine_distance(lat, lng, gig['location_lat'], gig['location_lng'])
                if distance <= max_distance:
                    gig_dict['distance'] = round(distance, 2)
                    result.append(gig_dict)
            else:
                result.append(gig_dict)
        
        # Sort by distance if location provided
        if lat and lng:
            result.sort(key=lambda x: x.get('distance', float('inf')))
    
    return jsonify({'gigs': result}), 200

@gigs_bp.route('/gigs/<int:gig_id>', methods=['GET'])
def get_gig(gig_id):
    db = get_db()
    gig = db.execute('''SELECT g.*, u.name as provider_name, u.rating as provider_rating,
                          u.email as provider_email, u.phone as provider_phone
                          FROM gigs g JOIN users u ON g.provider_id = u.id
                          WHERE g.id = ?''', (gig_id,)).fetchone()
    
    if not gig:
        return jsonify({'error': 'Gig not found'}), 404
    
    return jsonify({'gig': dict(gig)}), 200

@gigs_bp.route('/gigs/recommended', methods=['GET'])
@auth_required
def get_recommended_gigs():
    user_id = session['user_id']
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    
    if not lat or not lng:
        return jsonify({'error': 'Location required for recommendations'}), 400
    
    db = get_db()
    
    # Get user profile
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    # Get all open gigs
    gigs = db.execute('''SELECT g.*, u.name as provider_name, u.rating as provider_rating
                           FROM gigs g JOIN users u ON g.provider_id = u.id
                           WHERE g.status = 'open' ''').fetchall()
    
    recommendations = []
    for gig in gigs:
        distance = haversine_distance(lat, lng, gig['location_lat'], gig['location_lng'])
        
        if distance <= 35:  # Within 35km radius
            gig_dict = dict(gig)
            gig_dict['distance'] = round(distance, 2)
            gig_dict['match_score'] = calculate_match_score(user, gig, distance)
            recommendations.append(gig_dict)
    
    # Sort by match score (descending)
    recommendations.sort(key=lambda x: x['match_score'], reverse=True)
    
    return jsonify({'recommendations': recommendations[:20]}), 200

@gigs_bp.route('/user/gigs', methods=['GET'])
@auth_required
def get_user_gigs():
    user_id = session['user_id']
    db = get_db()
    gigs = db.execute('''SELECT * FROM gigs WHERE provider_id = ? ORDER BY created_at DESC''', 
                       (user_id,)).fetchall()
    return jsonify({'gigs': [dict(gig) for gig in gigs]}), 200

# Application endpoints
@gigs_bp.route('/gigs/<int:gig_id>/apply', methods=['POST'])
@auth_required
def apply_to_gig(gig_id):
    data = request.json
    seeker_id = session['user_id']
    
    db = get_db()
    
    try:
        # Check if gig exists and is open
        gig = db.execute('SELECT * FROM gigs WHERE id = ?', (gig_id,)).fetchone()
        if not gig:
            return jsonify({'error': 'Gig not found'}), 404
        
        if gig['status'] != 'open':
            return jsonify({'error': 'Gig is no longer available'}), 400
        
        # Check if user is trying to apply to their own gig
        if gig['provider_id'] == seeker_id:
            return jsonify({'error': 'Cannot apply to your own gig'}), 400
        
        # Check if already applied
        existing = db.execute('SELECT id FROM applications WHERE gig_id = ? AND seeker_id = ?',
                           (gig_id, seeker_id)).fetchone()
        if existing:
            return jsonify({'error': 'Already applied to this gig'}), 400
        
        # Create application
        c = db.cursor()
        c.execute('''INSERT INTO applications (gig_id, seeker_id, message)
                     VALUES (?, ?, ?)''',
                  (gig_id, seeker_id, data.get('message', '')))
        app_id = c.lastrowid
        
        db.commit()
        
        return jsonify({
            'message': 'Application submitted successfully', 
            'application_id': app_id
        }), 201
        
    except Exception as e:
        print(f"Error applying to gig: {str(e)}")  # Debug print
        db.rollback()
        return jsonify({'error': 'Failed to submit application'}), 500

@gigs_bp.route('/user/applications', methods=['GET'])
@auth_required
def get_user_applications():
    user_id = session['user_id']
    db = get_db()
    applications = db.execute('''SELECT a.*, g.title, g.category, u.name as provider_name 
                                   FROM applications a 
                                   JOIN gigs g ON a.gig_id = g.id 
                                   JOIN users u ON g.provider_id = u.id
                                   WHERE a.seeker_id = ? ORDER BY a.created_at DESC''', 
                               (user_id,)).fetchall()
    return jsonify({'applications': [dict(app) for app in applications]}), 200

@gigs_bp.route('/gigs/<int:gig_id>/applications', methods=['GET'])
@auth_required
def get_gig_applications(gig_id):
    db = get_db()
    
    # Verify user owns the gig
    gig = db.execute('SELECT provider_id FROM gigs WHERE id = ?', (gig_id,)).fetchone()
    if not gig or gig['provider_id'] != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    applications = db.execute('''SELECT a.*, u.name as seeker_name, u.email as seeker_email, 
                                u.phone as seeker_phone, u.skills as seeker_skills,
                                u.rating as seeker_rating
                                FROM applications a 
                                JOIN users u ON a.seeker_id = u.id
                                WHERE a.gig_id = ? ORDER BY a.created_at DESC''', 
                            (gig_id,)).fetchall()
    
    return jsonify({'applications': [dict(app) for app in applications]}), 200

@gigs_bp.route('/applications/<int:app_id>/status', methods=['PUT'])
@auth_required
def update_application_status(app_id):
    data = request.json
    status = data.get('status')
    
    if status not in ['accepted', 'rejected']:
        return jsonify({'error': 'Invalid status. Must be "accepted" or "rejected"'}), 400
    
    db = get_db()
    
    try:
        # Verify user is the gig provider
        app = db.execute('''SELECT a.*, g.provider_id, g.title
                          FROM applications a JOIN gigs g ON a.gig_id = g.id
                          WHERE a.id = ?''', (app_id,)).fetchone()
        
        if not app:
            return jsonify({'error': 'Application not found'}), 404
            
        if app['provider_id'] != session['user_id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update application status
        db.execute('UPDATE applications SET status = ? WHERE id = ?', (status, app_id))
        
        # If accepted, update gig status and assign seeker
        if status == 'accepted':
            db.execute('UPDATE gigs SET status = ?, seeker_id = ? WHERE id = ?',
                      ('assigned', app['seeker_id'], app['gig_id']))
            
            # Reject all other applications for this gig
            db.execute('UPDATE applications SET status = ? WHERE gig_id = ? AND id != ?',
                      ('rejected', app['gig_id'], app_id))
            
            # Create a contract automatically
            db.execute('''INSERT INTO contracts (gig_id, provider_id, seeker_id, terms, pay, date)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                      (app['gig_id'], app['provider_id'], app['seeker_id'],
                       f"Contract for gig: {app['title']}",  # Basic terms
                       0,  # Pay will be set later
                       datetime.now().strftime('%Y-%m-%d')))
        
        db.commit()
        
        return jsonify({'message': f'Application {status} successfully'}), 200
        
    except Exception as e:
        print(f"Error updating application status: {str(e)}")
        db.rollback()
        return jsonify({'error': 'Failed to update application status'}), 500

# Debug endpoint
@gigs_bp.route('/debug/gigs', methods=['GET'])
def debug_gigs():
    """Debug endpoint to check gigs and applications"""
    db = get_db()
    
    gigs = db.execute('SELECT * FROM gigs').fetchall()
    applications = db.execute('SELECT * FROM applications').fetchall()
    users = db.execute('SELECT id, name, email FROM users').fetchall()
    
    return jsonify({
        'gigs': [dict(gig) for gig in gigs],
        'applications': [dict(app) for app in applications],
        'users': [dict(user) for user in users]
    }), 200