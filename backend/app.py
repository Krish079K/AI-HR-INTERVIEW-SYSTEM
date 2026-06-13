from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os

from config import Config
from database import init_db
from routes.auth import auth_bp
from routes.interviews import interviews_bp
from routes.admin import admin_bp

app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS for frontend connection (Angular default is port 4200)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize JWT Manager
jwt = JWTManager(app)

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(interviews_bp, url_prefix='/api/interviews')
app.register_blueprint(admin_bp, url_prefix='/api/admin')

# Route to serve uploads (reports, audio files)
@app.route('/api/uploads/<path:filename>', methods=['GET'])
def serve_uploads(filename):
    return send_from_directory(Config.UPLOAD_FOLDER, filename)

# Custom JWT Error Handlers
@jwt.unauthorized_loader
def unauthorized_response(callback):
    return jsonify({"message": "Missing authorization headers"}), 401

@jwt.invalid_token_loader
def invalid_token_response(callback):
    return jsonify({"message": "Invalid auth token"}), 401

@jwt.expired_token_loader
def expired_token_response(jwt_header, jwt_payload):
    return jsonify({"message": "Auth token has expired"}), 401

# Health Check Route
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "database": os.path.exists(Config.DATABASE),
        "message": "AI Virtual HR Interviewer backend is running."
    }), 200

# Initialize DB on Startup
with app.app_context():
    try:
        init_db()
        print("Database checked/initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == '__main__':
    # Run the server on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
