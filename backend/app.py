"""
E-Voting System Backend
A secure blockchain-based voting system API
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import bcrypt
from web3 import Web3
import json

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///evoting.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Blockchain setup
BLOCKCHAIN_PROVIDER = os.getenv('BLOCKCHAIN_PROVIDER', 'http://127.0.0.1:8545')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS', '')

try:
    w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_PROVIDER))
    blockchain_connected = w3.is_connected()
except:
    w3 = None
    blockchain_connected = False

# Load contract ABI
CONTRACT_ABI = []  # Add your contract ABI here after compilation

# ==================== Database Models ====================

class User(db.Model):
    """User model for voter authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    voter_id = db.Column(db.String(50), unique=True, nullable=True)  # Aadhar/College ID
    wallet_address = db.Column(db.String(42), unique=True, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # FIX 1: Ensure password hash is stored as a string (utf-8)
    def set_password(self, password):
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        self.password_hash = hashed.decode('utf-8') 
    
    # FIX 2: Ensure comparison works with stored string hashes
    def check_password(self, password):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except:
            return False
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'voter_id': self.voter_id,
            'wallet_address': self.wallet_address,
            'is_verified': self.is_verified,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Election(db.Model):
    """Election model for storing election metadata"""
    __tablename__ = 'elections'
    
    id = db.Column(db.Integer, primary_key=True)
    blockchain_id = db.Column(db.Integer, unique=True, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    candidates = db.relationship('Candidate', backref='election', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'blockchain_id': self.blockchain_id,
            'name': self.name,
            'description': self.description,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'candidates': [c.to_dict() for c in self.candidates]
        }


class Candidate(db.Model):
    """Candidate model for storing candidate information"""
    __tablename__ = 'candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    blockchain_id = db.Column(db.Integer, nullable=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    party = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'blockchain_id': self.blockchain_id,
            'election_id': self.election_id,
            'name': self.name,
            'party': self.party,
            'description': self.description,
            'image_url': self.image_url
        }


class Vote(db.Model):
    """Vote record model (for audit purposes - actual votes on blockchain)"""
    __tablename__ = 'votes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id'), nullable=False)
    transaction_hash = db.Column(db.String(66), unique=True, nullable=True)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== Helper Functions ====================

def admin_required(fn):
    """Decorator to require admin privileges"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin privileges required'}), 403
        return fn(*args, **kwargs)
    return wrapper


def verified_voter_required(fn):
    """Decorator to require verified voter status"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or not user.is_verified:
            return jsonify({'error': 'Verified voter status required'}), 403
        return fn(*args, **kwargs)
    return wrapper


# ==================== API Routes ====================

# ----- Health Check -----
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'blockchain_connected': blockchain_connected,
        'timestamp': datetime.utcnow().isoformat()
    })


# ----- Authentication Routes -----
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['email', 'password', 'full_name']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409
    
    # Create new user
    user = User(
        email=data['email'],
        full_name=data['full_name'],
        voter_id=data.get('voter_id'),
        wallet_address=data.get('wallet_address')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'Registration successful',
        'user': user.to_dict()
    }), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user and return JWT tokens"""
    data = request.get_json()
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    
    
    # access_token = create_access_token(identity=user.id)
    # refresh_token = create_refresh_token(identity=user.id)
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    })


@app.route('/api/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({'access_token': access_token})


@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({'user': user.to_dict()})


@app.route('/api/auth/update-profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if 'full_name' in data:
        user.full_name = data['full_name']
    if 'voter_id' in data:
        user.voter_id = data['voter_id']
    if 'wallet_address' in data:
        user.wallet_address = data['wallet_address']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Profile updated successfully',
        'user': user.to_dict()
    })


# ----- Admin Routes -----
@app.route('/api/admin/verify-voter/<int:user_id>', methods=['POST'])
@admin_required
def verify_voter(user_id):
    """Verify a voter (admin only)"""
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.is_verified = True
    db.session.commit()
    
    return jsonify({
        'message': 'Voter verified successfully',
        'user': user.to_dict()
    })


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_all_users():
    """Get all users (admin only)"""
    users = User.query.all()
    return jsonify({
        'users': [u.to_dict() for u in users]
    })


@app.route('/api/admin/make-admin/<int:user_id>', methods=['POST'])
@admin_required
def make_admin(user_id):
    """Make a user an admin (admin only)"""
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.is_admin = True
    db.session.commit()
    
    return jsonify({
        'message': 'User is now an admin',
        'user': user.to_dict()
    })


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)"""
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.is_admin:
        return jsonify({'error': 'Cannot delete admin users'}), 400
    
    # Delete user's votes first (foreign key constraint)
    Vote.query.filter_by(user_id=user_id).delete()
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'message': 'User deleted successfully'})


# ----- Election Routes -----
@app.route('/api/elections', methods=['GET'])
def get_elections():
    """Get all elections"""
    elections = Election.query.order_by(Election.created_at.desc()).all()
    return jsonify({
        'elections': [e.to_dict() for e in elections]
    })


@app.route('/api/elections/<int:election_id>', methods=['GET'])
def get_election(election_id):
    """Get a specific election"""
    election = db.session.get(Election, election_id)
    
    if not election:
        return jsonify({'error': 'Election not found'}), 404
    
    return jsonify({'election': election.to_dict()})

def parse_datetime(value):
    # Accepts:
    # 2026-01-31T13:52
    # 2026-01-31T13:52:00
    # 2026-01-31T13:52:00Z
    # 2026-01-31T13:52:00+00:00
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.fromisoformat(value)   

@app.route('/api/elections', methods=['POST'])
@admin_required
def create_election():
    user_id = get_jwt_identity()
    data = request.get_json()

    try:
        start_time = parse_datetime(data['start_time']).astimezone(ZoneInfo("Asia/Kolkata"))
        end_time = parse_datetime(data['end_time']).astimezone(ZoneInfo("Asia/Kolkata"))

        if end_time <= start_time:
            return jsonify({"error": "End time must be after start time"}), 400

    except Exception as e:
        print(f"Date Parsing Error: {e}")
        return jsonify({"error": "Invalid date format. Expected YYYY-MM-DDTHH:MM"}), 400

    election = Election(
        name=data['name'],
        description=data.get('description', ''),
        start_time=start_time,   # ✅ datetime
        end_time=end_time,       # ✅ datetime
        created_by=user_id
    )

    db.session.add(election)
    db.session.commit()

    return jsonify({
        'message': 'Election created successfully',
        'election': election.to_dict()
    }), 201


@app.route('/api/elections/<int:election_id>', methods=['PUT'])
@admin_required
def update_election(election_id):
    """Update an election (admin only)"""
    election = db.session.get(Election, election_id)
    data = request.get_json()
    
    if not election:
        return jsonify({'error': 'Election not found'}), 404
    
    if 'name' in data:
        election.name = data['name']
    if 'description' in data:
        election.description = data['description']
    if 'is_active' in data:
        election.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Election updated successfully',
        'election': election.to_dict()
    })


@app.route('/api/elections/<int:election_id>/toggle', methods=['POST'])
@admin_required
def toggle_election(election_id):
    """Toggle election active status (admin only)"""
    election = db.session.get(Election, election_id)
    
    if not election:
        return jsonify({'error': 'Election not found'}), 404
    
    election.is_active = not election.is_active
    db.session.commit()
    
    return jsonify({
        'message': f'Election {"activated" if election.is_active else "deactivated"} successfully',
        'election': election.to_dict()
    })


# ----- Candidate Routes -----
@app.route('/api/elections/<int:election_id>/candidates', methods=['GET'])
def get_candidates(election_id):
    """Get all candidates for an election"""
    election = db.session.get(Election, election_id)
    
    if not election:
        return jsonify({'error': 'Election not found'}), 404
    
    return jsonify({
        'candidates': [c.to_dict() for c in election.candidates]
    })


@app.route('/api/elections/<int:election_id>/candidates', methods=['POST'])
@admin_required
def add_candidate(election_id):
    """Add a candidate to an election (admin only)"""
    election = db.session.get(Election, election_id)
    data = request.get_json()
    
    if not election:
        return jsonify({'error': 'Election not found'}), 404
    
    if datetime.utcnow() >= election.start_time:
        return jsonify({'error': 'Cannot add candidates after election starts'}), 400
    
    if not data.get('name'):
        return jsonify({'error': 'Candidate name is required'}), 400
    
    candidate = Candidate(
        election_id=election_id,
        name=data['name'],
        party=data.get('party', ''),
        description=data.get('description', ''),
        image_url=data.get('image_url', '')
    )
    
    db.session.add(candidate)
    db.session.commit()
    
    return jsonify({
        'message': 'Candidate added successfully',
        'candidate': candidate.to_dict()
    }), 201


def to_utc(dt_naive):
    # Treat naive datetime as IST
    ist = dt_naive.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return ist.astimezone(ZoneInfo("UTC"))


# ----- Voting Routes -----
@app.route('/api/elections/<int:election_id>/vote', methods=['POST'])
@verified_voter_required
def cast_vote(election_id):
    """Cast a vote in an election"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    
    election = db.session.get(Election, election_id)
    
    if not election:
        return jsonify({'error': 'Election not found'}), 404
    
    # Check if election is active and within time bounds
    now = datetime.now(timezone.utc)

    start_time = to_utc(election.start_time)
    end_time = to_utc(election.end_time)
    if not election.is_active:
        return jsonify({'error': 'Election is not active'}), 400
    if now < start_time:
        return jsonify({'error': 'Election has not started yet'}), 400
    if now > end_time:
        return jsonify({'error': 'Election has ended'}), 400
    
    # Check if user has already voted
    existing_vote = Vote.query.filter_by(user_id=user_id, election_id=election_id).first()
    if existing_vote:
        return jsonify({'error': 'You have already voted in this election'}), 400
    
    # Validate candidate
    candidate_id = data.get('candidate_id')
    if not candidate_id:
        return jsonify({'error': 'Candidate ID is required'}), 400
    
    candidate = Candidate.query.filter_by(id=candidate_id, election_id=election_id).first()
    if not candidate:
        return jsonify({'error': 'Invalid candidate'}), 400
    
    # Record the vote (transaction hash would come from blockchain in production)
    vote = Vote(
        user_id=user_id,
        election_id=election_id,
        candidate_id=candidate_id,
        transaction_hash=None  # Would be set after blockchain transaction
    )
    
    db.session.add(vote)
    db.session.commit()
    
    return jsonify({
        'message': 'Vote cast successfully',
        'vote_id': vote.id
    })


@app.route('/api/elections/<int:election_id>/has-voted', methods=['GET'])
@jwt_required()
def has_voted(election_id):
    """Check if current user has voted in an election"""
    user_id = get_jwt_identity()
    
    vote = Vote.query.filter_by(user_id=user_id, election_id=election_id).first()
    
    return jsonify({
        'has_voted': vote is not None
    })
def ensure_aware(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

@app.route('/api/elections/<int:election_id>/results', methods=['GET'])
def get_results(election_id):
    """Get election results (only after election ends)"""
    election = db.session.get(Election, election_id)
    
    if not election:
        return jsonify({'error': 'Election not found'}), 404

    now = datetime.now(timezone.utc)
    end_time = to_utc(election.end_time)  
    
    # Allow viewing results only after election ends
    if now <=end_time:
        return jsonify({'error': 'Results are available only after the election ends'}), 400
    
    # Get vote counts
    results = []
    total_votes = Vote.query.filter_by(election_id=election_id).count()
    
    for candidate in election.candidates:
        vote_count = Vote.query.filter_by(
            election_id=election_id,
            candidate_id=candidate.id
        ).count()
        percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
        results.append({
            'candidate': candidate.to_dict(),
            'votes': vote_count,
            'percentage': round(percentage, 1)
        })
    
    # Sort results by votes (highest first)
    results.sort(key=lambda x: x['votes'], reverse=True)
    
    return jsonify({
        'election': election.to_dict(),
        'results': results,
        'total_votes': total_votes
    })


# ----- Blockchain Routes -----
@app.route('/api/blockchain/status', methods=['GET'])
def blockchain_status():
    """Get blockchain connection status"""
    if not w3:
        return jsonify({
            'connected': False,
            'error': 'Web3 not initialized'
        })
    
    try:
        connected = w3.is_connected()
        block_number = w3.eth.block_number if connected else None
        
        return jsonify({
            'connected': connected,
            'block_number': block_number,
            'network_id': w3.net.version if connected else None
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e)
        })


# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


# ==================== Database Initialization ====================

def init_db():
    """Initialize the database and create default admin"""
    db.create_all()
    
    # Create default admin if not exists
    admin = User.query.filter_by(email='admin@evoting.com').first()
    if not admin:
        admin = User(
            email='admin@evoting.com',
            full_name='System Admin',
            is_admin=True,
            is_verified=True
        )
        admin.set_password('admin123') 
        db.session.add(admin)
        db.session.commit()
        print('SUCCESS: Default admin created: admin@evoting.com / admin123')

# FIX 3: Initialize database properly within application context
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
