from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import json
from database import get_db_connection, DBIntegrityError
 
auth_bp = Blueprint('auth', __name__)
 
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing request data"}), 400
        
    name = data.get('name')
    email = data.get('email', '').strip().lower()
    password = data.get('password')
    
    if not name or not email or not password:
        return jsonify({"message": "Missing name, email, or password"}), 400
        
    password_hash = generate_password_hash(password)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'candidate')",
            (name, email, password_hash)
        )
        conn.commit()
        
        # Get the newly created user's ID
        user_id = cursor.lastrowid
        access_token = create_access_token(identity=json.dumps({"id": user_id, "email": email, "role": "candidate"}))
        
        return jsonify({
            "message": "User registered successfully",
            "token": access_token,
            "user": {"id": user_id, "name": name, "email": email, "role": "candidate"}
        }), 201
        
    except DBIntegrityError:
        return jsonify({"message": "User with this email already exists"}), 409
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing request data"}), 400
        
    email = data.get('email', '').strip().lower()
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"message": "Missing email or password"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
        user = cursor.fetchone()
        
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({"message": "Invalid email or password"}), 401
            
        access_token = create_access_token(identity=json.dumps({"id": user['id'], "email": user['email'], "role": user['role']}))
        
        return jsonify({
            "token": access_token,
            "user": {
                "id": user['id'],
                "name": user['name'],
                "email": user['email'],
                "role": user['role']
            }
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    identity = json.loads(get_jwt_identity())
    user_id = identity.get('id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, name, email, role, created_at FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"message": "User not found"}), 440
            
        return jsonify({
            "id": user['id'],
            "name": user['name'],
            "email": user['email'],
            "role": user['role'],
            "created_at": user['created_at']
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()


import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config

RESET_CODES = {}

def send_reset_email(to_email, code):
    # Retrieve SMTP credentials from config
    mail_server = getattr(Config, 'MAIL_SERVER', 'smtp.gmail.com')
    mail_port = getattr(Config, 'MAIL_PORT', 587)
    mail_username = getattr(Config, 'MAIL_USERNAME', '')
    mail_password = getattr(Config, 'MAIL_PASSWORD', '')
    
    if not mail_username or not mail_password:
        print(f"SMTP Credentials not configured. Simulated reset code for {to_email}: {code}")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = mail_username
        msg['To'] = to_email
        msg['Subject'] = "AI Virtual HR Interviewer - Password Reset Code"
        
        body = f"""Hello,

You recently requested to reset your password for the AI Virtual HR Interviewer platform.

Your 6-digit verification code is: {code}

Please enter this code on the reset page to set a new password. If you did not request this, please ignore this email.

Best regards,
AI Virtual HR Interviewer Team
"""
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect and send
        server = smtplib.SMTP(mail_server, mail_port)
        server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        print(f"Password reset email successfully sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({"message": "Email is required"}), 400
        
    email = data.get('email', '').strip().lower()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"message": "No account found with this email address."}), 404
            
        # Generate a 6-digit verification code
        code = str(random.randint(100000, 999999))
        RESET_CODES[email] = code
        
        # Dispatch SMTP email
        email_sent = send_reset_email(email, code)
        
        message_detail = "Reset code generated successfully."
        if email_sent:
            message_detail += " Password reset code has been sent to your email."
        else:
            message_detail += " Simulated dispatch (check dev console or copy code below)."
            
        return jsonify({
            "message": message_detail,
            "email": email,
            "code": code,
            "email_sent": email_sent
        }), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    if not data or not all(k in data for k in ('email', 'code', 'new_password')):
        return jsonify({"message": "Missing email, code, or new_password"}), 400
        
    email = data.get('email', '').strip().lower()
    code = data.get('code').strip()
    new_password = data.get('new_password')
    
    if len(new_password) < 6:
        return jsonify({"message": "Password must be at least 6 characters"}), 400
        
    if email not in RESET_CODES or RESET_CODES[email] != code:
        return jsonify({"message": "Invalid or expired verification code."}), 400
        
    password_hash = generate_password_hash(new_password)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET password_hash = ? WHERE LOWER(email) = ?", (password_hash, email))
        conn.commit()
        
        # Clear the code
        RESET_CODES.pop(email, None)
        
        return jsonify({"message": "Password reset successfully. Please sign in with your new credentials."}), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

