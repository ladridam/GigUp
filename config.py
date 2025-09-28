# config.py - Configuration settings
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE = os.getenv('DATABASE_URL', 'gigup.db')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # Application settings
    MAX_DISTANCE_KM = 35
    DEFAULT_USER_RATING = 0.0
    
    # Verification settings
    VERIFICATION_CODE_EXPIRY_HOURS = 24
    VERIFICATION_CODE_LENGTH = 8

config = Config