from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import json
from database import get_db_connection

admin_bp = Blueprint('admin', __name__)

def check_admin_role():
    identity_str = get_jwt_identity()
    if not identity_str:
        return False
    try:
        identity = json.loads(identity_str)
        if identity.get('role') != 'admin':
            return False
        return True
    except Exception:
        return False

@admin_bp.route('/questions', methods=['GET'])
@jwt_required()
def get_all_questions():
    if not check_admin_role():
        return jsonify({"message": "Admin access required"}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM questions ORDER BY category, id ASC")
        questions = cursor.fetchall()
        return jsonify([dict(q) for q in questions]), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@admin_bp.route('/questions', methods=['POST'])
@jwt_required()
def create_question():
    if not check_admin_role():
        return jsonify({"message": "Admin access required"}), 403
        
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing request body"}), 400
        
    category = data.get('category')
    question_text = data.get('question_text')
    keywords = data.get('keywords')
    ideal_answer = data.get('ideal_answer', '')
    
    if not category or not question_text or not keywords:
        return jsonify({"message": "Missing category, question_text, or keywords"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO questions (category, question_text, keywords, ideal_answer) VALUES (?, ?, ?, ?)",
            (category, question_text, keywords, ideal_answer)
        )
        conn.commit()
        return jsonify({"message": "Question created successfully", "id": cursor.lastrowid}), 201
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@admin_bp.route('/questions/<int:question_id>', methods=['PUT'])
@jwt_required()
def update_question(question_id):
    if not check_admin_role():
        return jsonify({"message": "Admin access required"}), 403
        
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing request body"}), 400
        
    category = data.get('category')
    question_text = data.get('question_text')
    keywords = data.get('keywords')
    ideal_answer = data.get('ideal_answer', '')
    
    if not category or not question_text or not keywords:
        return jsonify({"message": "Missing category, question_text, or keywords"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE questions SET category = ?, question_text = ?, keywords = ?, ideal_answer = ? WHERE id = ?",
            (category, question_text, keywords, ideal_answer, question_id)
        )
        conn.commit()
        return jsonify({"message": "Question updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@admin_bp.route('/questions/<int:question_id>', methods=['DELETE'])
@jwt_required()
def delete_question(question_id):
    if not check_admin_role():
        return jsonify({"message": "Admin access required"}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()
        return jsonify({"message": "Question deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@admin_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_system_stats():
    if not check_admin_role():
        return jsonify({"message": "Admin access required"}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'candidate'")
        total_candidates = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM interviews WHERE status = 'completed'")
        total_interviews = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(overall_score) FROM interviews WHERE status = 'completed'")
        avg_score = cursor.fetchone()[0] or 0.0
        
        return jsonify({
            "total_candidates": total_candidates,
            "total_interviews": total_interviews,
            "average_score": round(avg_score, 1)
        }), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@admin_bp.route('/candidates', methods=['GET'])
@jwt_required()
def get_candidates():
    if not check_admin_role():
        return jsonify({"message": "Admin access required"}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT u.id, u.name, u.email, u.created_at, 
                   COUNT(i.id) as interviews_count, AVG(i.overall_score) as avg_score
            FROM users u
            LEFT JOIN interviews i ON u.id = i.user_id AND i.status = 'completed'
            WHERE u.role = 'candidate'
            GROUP BY u.id
            ORDER BY u.name ASC
        ''')
        candidates = cursor.fetchall()
        return jsonify([dict(c) for c in candidates]), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()
