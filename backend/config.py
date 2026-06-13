import os
from datetime import timedelta

class Config:
    # Base Directory
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ai-interviewer-super-secret-key-1337')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-ai-interviewer-secret-key-9988')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # Database
    DATABASE = os.path.join(BASE_DIR, 'interviewer.db')
    
    # Upload Configurations
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    AUDIO_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, 'audio')
    RESUME_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, 'resumes')
    
    # Ensure directories exist
    os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)
    os.makedirs(RESUME_UPLOAD_DIR, exist_ok=True)
    
    # Allowed File Extensions
    ALLOWED_AUDIO_EXTENSIONS = {'wav', 'webm', 'ogg', 'mp3'}
    ALLOWED_RESUME_EXTENSIONS = {'pdf', 'doc', 'docx'}
    
    @staticmethod
    def allowed_file(filename, allowed_extensions):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

    # SMTP Configuration (For real password recovery emails)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USERNAME = ''  # Enter your sender gmail here (e.g. 'sender@gmail.com')
    MAIL_PASSWORD = ''  # Enter your Google App Password here

    # Database Selection (sqlite, mysql, or postgres)
    DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')

    # MySQL Configurations (ignored if DB_TYPE is not 'mysql')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'ai_interviewer')

    # PostgreSQL Configurations (ignored if DB_TYPE is not 'postgres')
    POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.environ.get('POSTGRES_PORT', 5432))
    POSTGRES_USER = os.environ.get('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', '')
    POSTGRES_DB = os.environ.get('POSTGRES_DB', 'ai_interviewer')


