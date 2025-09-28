# models/user.py - Database models and initialization
import sqlite3
from flask import g
from werkzeug.security import generate_password_hash

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('gigup.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app):
    app.teardown_appcontext(close_db)
    
    with app.app_context():
        db = get_db()
        
        # Users table
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            skills TEXT,
            bio TEXT,
            rating REAL DEFAULT 0.0,
            total_ratings INTEGER DEFAULT 0,
            verified_email BOOLEAN DEFAULT 0,
            verified_phone BOOLEAN DEFAULT 0,
            verified_social BOOLEAN DEFAULT 0,
            is_approved BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Gigs table
        db.execute('''CREATE TABLE IF NOT EXISTS gigs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            skills_required TEXT,
            description TEXT,
            date_time TEXT NOT NULL,
            duration TEXT,
            pay REAL NOT NULL,
            location_lat REAL NOT NULL,
            location_lng REAL NOT NULL,
            location_address TEXT,
            status TEXT DEFAULT 'open',
            seeker_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (provider_id) REFERENCES users (id),
            FOREIGN KEY (seeker_id) REFERENCES users (id)
        )''')
        
        # Contracts table
        db.execute('''CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gig_id INTEGER NOT NULL,
            provider_id INTEGER NOT NULL,
            seeker_id INTEGER NOT NULL,
            terms TEXT NOT NULL,
            pay REAL NOT NULL,
            hours INTEGER,
            date TEXT NOT NULL,
            provider_signature TEXT,
            seeker_signature TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            signed_at TIMESTAMP,
            FOREIGN KEY (gig_id) REFERENCES gigs (id),
            FOREIGN KEY (provider_id) REFERENCES users (id),
            FOREIGN KEY (seeker_id) REFERENCES users (id)
        )''')
        
        # Applications table
        db.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gig_id INTEGER NOT NULL,
            seeker_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gig_id) REFERENCES gigs (id),
            FOREIGN KEY (seeker_id) REFERENCES users (id)
        )''')
        
        # Reviews table
        db.execute('''CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reviewer_id INTEGER NOT NULL,
            reviewed_id INTEGER NOT NULL,
            gig_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reviewer_id) REFERENCES users (id),
            FOREIGN KEY (reviewed_id) REFERENCES users (id),
            FOREIGN KEY (gig_id) REFERENCES gigs (id)
        )''')
        
        # Verification codes table
        db.execute('''CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            type TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        
        # Create admin user if not exists
        admin = db.execute('SELECT id FROM users WHERE email = ?', ('admin@gigup.com',)).fetchone()
        if not admin:
            admin_hash = generate_password_hash('admin123')
            db.execute('''INSERT INTO users (name, email, phone, password_hash, role, is_approved, verified_email)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       ('Admin', 'admin@gigup.com', '0000000000', admin_hash, 'admin', 1, 1))
            print("Admin user created: admin@gigup.com / admin123")
        
        db.commit()