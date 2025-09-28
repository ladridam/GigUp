# routes/contracts.py - Contracts routes
from flask import Blueprint, request, jsonify, session
from models.user import get_db
from routes.auth import auth_required

contracts_bp = Blueprint('contracts', __name__)

@contracts_bp.route('/contracts', methods=['POST'])
@auth_required
def create_contract():
    data = request.json
    provider_id = session['user_id']
    
    required = ['gig_id', 'seeker_id', 'terms', 'pay', 'date']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    db = get_db()
    try:
        c = db.cursor()
        c.execute('''INSERT INTO contracts (gig_id, provider_id, seeker_id, terms,
                     pay, hours, date)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (data['gig_id'], provider_id, data['seeker_id'], data['terms'],
                   data['pay'], data.get('hours'), data['date']))
        contract_id = c.lastrowid
        db.commit()
        
        return jsonify({'message': 'Contract created', 'contract_id': contract_id}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to create contract'}), 500

@contracts_bp.route('/contracts/<int:contract_id>/sign', methods=['POST'])
@auth_required
def sign_contract(contract_id):
    data = request.json
    user_id = session['user_id']
    signature = data.get('signature')  # Base64 encoded signature from canvas
    
    if not signature:
        return jsonify({'error': 'Signature required'}), 400
    
    db = get_db()
    try:
        contract = db.execute('SELECT * FROM contracts WHERE id = ?', 
                               (contract_id,)).fetchone()
        
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Determine if provider or seeker is signing
        if user_id == contract['provider_id']:
            db.execute('UPDATE contracts SET provider_signature = ? WHERE id = ?',
                        (signature, contract_id))
        elif user_id == contract['seeker_id']:
            db.execute('UPDATE contracts SET seeker_signature = ? WHERE id = ?',
                        (signature, contract_id))
        else:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if both parties have signed
        updated = db.execute('SELECT * FROM contracts WHERE id = ?', 
                              (contract_id,)).fetchone()
        if updated['provider_signature'] and updated['seeker_signature']:
            db.execute('''UPDATE contracts SET status = 'signed', signed_at = CURRENT_TIMESTAMP
                           WHERE id = ?''', (contract_id,))
            # Update gig status
            db.execute('UPDATE gigs SET status = ? WHERE id = ?',
                        ('in_progress', updated['gig_id']))
        
        db.commit()
        return jsonify({'message': 'Contract signed successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to sign contract'}), 500

@contracts_bp.route('/user/contracts', methods=['GET'])
@auth_required
def get_user_contracts():
    user_id = session['user_id']
    db = get_db()
    contracts = db.execute('''SELECT c.*, g.title, u1.name as provider_name, u2.name as seeker_name
                               FROM contracts c
                               JOIN gigs g ON c.gig_id = g.id
                               JOIN users u1 ON c.provider_id = u1.id
                               JOIN users u2 ON c.seeker_id = u2.id
                               WHERE c.provider_id = ? OR c.seeker_id = ?
                               ORDER BY c.created_at DESC''',
                           (user_id, user_id)).fetchall()
    return jsonify({'contracts': [dict(contract) for contract in contracts]}), 200