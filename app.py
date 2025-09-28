# app.py - Main Flask application
import os
from flask import Flask, render_template
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DATABASE'] = os.getenv('DATABASE_URL', 'gigup.db')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    # CORS configuration
    CORS(app, supports_credentials=True, origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000", 
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:5001",
        "http://127.0.0.1:5001"
    ])
    
    # Import and register blueprints
    try:
        from routes.auth import auth_bp
        from routes.gigs import gigs_bp
        from routes.contracts import contracts_bp
        from routes.admin import admin_bp
        
        app.register_blueprint(auth_bp, url_prefix='/api')
        app.register_blueprint(gigs_bp, url_prefix='/api')
        app.register_blueprint(contracts_bp, url_prefix='/api')
        app.register_blueprint(admin_bp, url_prefix='/api/admin')
        
        print("Blueprints registered successfully")
    except ImportError as e:
        print(f"Error importing blueprints: {e}")
    
    # Initialize database
    try:
        from models.user import init_db
        init_db(app)
        print("Database initialized successfully")
    except ImportError as e:
        print(f"Error initializing database: {e}")
    
    # Frontend routes
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/login')
    def login_page():
        return render_template('login.html')
    
    @app.route('/signup')
    def signup_page():
        return render_template('signup.html')
    
    @app.route('/admin')
    def admin_page():
        return render_template('admin.html')
    
    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')
    
    @app.route('/gigs')
    def browse_gigs():
        return render_template('gigs.html')
    
    @app.route('/gig/<int:gig_id>')
    def gig_detail(gig_id):
        return render_template('gig_detail.html') #removed gig_id=gig_id

    @app.route('/create-gig')
    def create_gig_page():
        return render_template('create_gig.html')
    
    @app.route('/my-gigs')
    def my_gigs():
        return render_template('my_gigs.html')
    
    @app.route('/profile')
    def profile():
        return render_template('profile.html')
    
    @app.route('/manage-applications')
    def manage_applications():
        return render_template('manage_applications.html')
    
    @app.route('/admin-dashboard')
    def admin_dashboard():
        return render_template('admin_dashboard.html')
    
    @app.route('/contract/<int:contract_id>')
    def contract_detail(contract_id):
        return render_template('contract_detail.html') #removed contract_id=contract_id
    
    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)  # CHANGED TO PORT 5001