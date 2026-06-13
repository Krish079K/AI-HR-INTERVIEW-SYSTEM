from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import json
import sqlite3
import uuid
from werkzeug.utils import secure_filename
from config import Config
from database import get_db_connection
from services.face_analysis import analyze_frame
from services.speech_analysis import transcribe_audio, get_audio_duration_and_amplitude, analyze_speech_content, analyze_communication
from services.report_generator import generate_pdf_report

interviews_bp = Blueprint('interviews', __name__)

@interviews_bp.route('/questions', methods=['GET'])
@jwt_required()
def get_questions():
    category = request.args.get('category')
    if not category:
        return jsonify({"message": "Category parameter is required"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, category, question_text, keywords FROM questions WHERE category = ? ORDER BY RANDOM() LIMIT 4", (category,))
        questions = cursor.fetchall()
        return jsonify([dict(q) for q in questions]), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@interviews_bp.route('/start', methods=['POST'])
@jwt_required()
def start_interview():
    identity = json.loads(get_jwt_identity())
    user_id = identity.get('id')
    
    data = request.get_json()
    if not data:
        return jsonify({"message": "Missing request body"}), 400
        
    category = data.get('category')
    if not category:
        return jsonify({"message": "Category is required"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO interviews (user_id, category, status) VALUES (?, ?, 'in_progress')",
            (user_id, category)
        )
        conn.commit()
        interview_id = cursor.lastrowid
        return jsonify({
            "interview_id": interview_id,
            "category": category,
            "status": "in_progress"
        }), 201
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@interviews_bp.route('/<int:interview_id>/frame', methods=['POST'])
@jwt_required()
def process_interview_frame(interview_id):
    """
    Receives base64 image data from the webcam and runs real-time analysis.
    """
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"message": "No image data received"}), 400
        
    base64_image = data['image']
    analysis = analyze_frame(base64_image)
    return jsonify(analysis), 200

@interviews_bp.route('/<int:interview_id>/question/<int:question_id>/answer', methods=['POST'])
@jwt_required()
def submit_question_answer(interview_id, question_id):
    """
    Uploads response audio (WAV), transcribes it, runs speech analysis, 
    stores the response row, and outputs a detailed score.
    """
    client_transcript = request.form.get('transcript', '').strip()
    
    # Save the file if uploaded
    audio_file = request.files.get('audio')
    audio_path = None
    
    if audio_file and audio_file.filename != '':
        filename = f"{interview_id}_{question_id}_{uuid.uuid4().hex}.wav"
        safe_name = secure_filename(filename)
        audio_path = os.path.join(Config.AUDIO_UPLOAD_DIR, safe_name)
        audio_file.save(audio_path)
    
    # Transcribe and analyze
    transcript = ""
    duration = 10.0  # default estimate
    rms = 1000.0
    std_dev = 500.0
    
    if audio_path:
        duration, rms, std_dev = get_audio_duration_and_amplitude(audio_path)
        # Attempt backend speech-to-text
        transcribed_text, err = transcribe_audio(audio_path)
        if transcribed_text:
            transcript = transcribed_text
        else:
            print(f"Backend transcription warning: {err}. Falling back to client-side transcription.")
            transcript = client_transcript
    else:
        # Fallback to client transcript directly if no audio file is provided (e.g. text-only/mock testing)
        transcript = client_transcript
        
    # Query the question expected keywords and ideal answer
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
        question = cursor.fetchone()
        if not question:
            return jsonify({"message": "Question not found"}), 404
            
        target_keywords = question['keywords']
        ideal_answer = question['ideal_answer']
        
        # Run NLP Analysis
        nlp_results = analyze_speech_content(transcript, target_keywords, ideal_answer)
        comm_results = analyze_communication(transcript, duration, rms, std_dev)
        
        # Calculate Eye Contact / Emotion average from recent frame ticks
        # In a real app, the client sends frame data and we compute it. Let's get the average of eye contact
        # Since frames are analyzed statelessly, the client can submit average eye contact ratio,
        # or we mock it with a realistic score based on face detection and eye contact indicators.
        eye_contact_ratio = float(request.form.get('eye_contact_ratio', 85.0))
        emotions_json = request.form.get('emotions', '[]')
        
        # Calculate scores
        # Technical score: 50% keyword matching + 50% semantic similarity
        tech_score = (nlp_results['keyword_score'] * 0.5) + (nlp_results['semantic_similarity'] * 0.5)
        # Handle zero-word speech
        if not transcript.strip():
            tech_score = 0.0
            
        comm_score = comm_results['communication_score']
        conf_score = comm_results['confidence_score']
        
        # Generate specific feedback
        feedback_points = []
        if tech_score < 50:
            feedback_points.append("Ensure you explain technical concepts using relevant industry keywords.")
        else:
            feedback_points.append("Good technical explanation and vocabulary.")
            
        if comm_results['wpm'] < 90:
            feedback_points.append("Try to speak a bit faster. Aim for a fluent pace.")
        elif comm_results['wpm'] > 160:
            feedback_points.append("You are speaking a bit too fast. Try to pause between sentences.")
        else:
            feedback_points.append("Perfect speaking pacing and communication clarity.")
            
        if eye_contact_ratio < 70:
            feedback_points.append("Maintain better eye contact by looking directly at the camera.")
            
        feedback_str = " | ".join(feedback_points)
        
        # Save to database
        cursor.execute('''
            INSERT INTO responses (
                interview_id, question_id, transcript, audio_path, speaking_speed, 
                eye_contact_ratio, confidence_score, communication_score, technical_score, 
                emotions_json, feedback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            interview_id, question_id, transcript, audio_path, comm_results['wpm'],
            eye_contact_ratio, conf_score, comm_score, tech_score, emotions_json, feedback_str
        ))
        conn.commit()
        
        return jsonify({
            "response_id": cursor.lastrowid,
            "transcript": transcript,
            "speaking_speed": comm_results['wpm'],
            "speaking_speed_status": comm_results['speaking_speed_status'],
            "eye_contact_ratio": eye_contact_ratio,
            "confidence_score": conf_score,
            "communication_score": comm_score,
            "technical_score": tech_score,
            "feedback": feedback_str
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"Database / analysis error: {str(e)}"}), 500
    finally:
        conn.close()

@interviews_bp.route('/<int:interview_id>/complete', methods=['POST'])
@jwt_required()
def complete_interview(interview_id):
    """
    Aggregates all question scores, updates the interview session row, 
    triggers the PDF report builder, and returns the dashboard analytics.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Fetch all responses for this interview
        cursor.execute("SELECT * FROM responses WHERE interview_id = ?", (interview_id,))
        responses = cursor.fetchall()
        
        if not responses:
            return jsonify({"message": "No responses found for this interview"}), 400
            
        # Calculate averages
        avg_tech = sum(r['technical_score'] for r in responses) / len(responses)
        avg_comm = sum(r['communication_score'] for r in responses) / len(responses)
        avg_conf = sum(r['confidence_score'] for r in responses) / len(responses)
        avg_eye = sum(r['eye_contact_ratio'] for r in responses) / len(responses)
        
        # Final weighted score
        overall_score = (avg_tech * 0.4) + (avg_comm * 0.25) + (avg_conf * 0.2) + (avg_eye * 0.15)
        
        # Generate summary feedback
        summary_bullets = []
        if avg_tech >= 75:
            summary_bullets.append("Showed excellent technical competence and keyword alignment.")
        else:
            summary_bullets.append("Focus on expanding on core details and using standard technical terms.")
            
        if avg_comm >= 80:
            summary_bullets.append("Exhibited strong communication with smooth, steady pacing.")
        else:
            summary_bullets.append("Aim to reduce pauses and manage speaking speed (aim for 120-150 WPM).")
            
        if avg_eye < 75:
            summary_bullets.append("Eye contact was low. Practice looking at the camera rather than the screen.")
        else:
            summary_bullets.append("Maintained natural, consistent eye contact during the session.")
            
        summary_feedback = " ".join(summary_bullets)
        
        # Update interview entry
        cursor.execute('''
            UPDATE interviews 
            SET status = 'completed', overall_score = ?, confidence_score = ?, 
                technical_score = ?, communication_score = ?, eye_contact_score = ?, 
                feedback_summary = ?
            WHERE id = ?
        ''', (
            round(overall_score, 1), round(avg_conf, 1), round(avg_tech, 1), 
            round(avg_comm, 1), round(avg_eye, 1), summary_feedback, interview_id
        ))
        conn.commit()
        
        # Generate PDF report
        pdf_filename = f"report_{interview_id}.pdf"
        pdf_path = os.path.join(Config.UPLOAD_FOLDER, pdf_filename)
        generate_pdf_report(Config.DATABASE, interview_id, pdf_path)
        
        return jsonify({
            "interview_id": interview_id,
            "overall_score": round(overall_score, 1),
            "technical_score": round(avg_tech, 1),
            "communication_score": round(avg_comm, 1),
            "confidence_score": round(avg_conf, 1),
            "eye_contact_score": round(avg_eye, 1),
            "feedback_summary": summary_feedback,
            "status": "completed"
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"Database aggregation error: {str(e)}"}), 500
    finally:
        conn.close()

@interviews_bp.route('/history', methods=['GET'])
@jwt_required()
def get_interview_history():
    identity = json.loads(get_jwt_identity())
    user_id = identity.get('id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM interviews WHERE user_id = ? AND status = 'completed' ORDER BY created_at DESC",
            (user_id,)
        )
        history = cursor.fetchall()
        return jsonify([dict(h) for h in history]), 200
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@interviews_bp.route('/<int:interview_id>/result', methods=['GET'])
@jwt_required()
def get_interview_result(interview_id):
    identity = json.loads(get_jwt_identity())
    user_id = identity.get('id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM interviews WHERE id = ? AND user_id = ?", (interview_id, user_id))
        interview = cursor.fetchone()
        
        if not interview:
            return jsonify({"message": "Interview session not found"}), 404
            
        cursor.execute('''
            SELECT r.*, q.question_text, q.keywords 
            FROM responses r
            JOIN questions q ON r.question_id = q.id 
            WHERE r.interview_id = ?
            ORDER BY r.id ASC
        ''', (interview_id,))
        responses = cursor.fetchall()
        
        # Serialize response dictionaries including parsing JSON fields
        serialized_responses = []
        for r in responses:
            r_dict = dict(r)
            try:
                r_dict['emotions'] = json.loads(r_dict['emotions_json']) if r_dict['emotions_json'] else []
            except Exception:
                r_dict['emotions'] = []
            serialized_responses.append(r_dict)
            
        return jsonify({
            "interview": dict(interview),
            "responses": serialized_responses
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@interviews_bp.route('/<int:interview_id>/report', methods=['GET'])
@jwt_required()
def download_report(interview_id):
    # Verify owner or admin
    identity = json.loads(get_jwt_identity())
    user_id = identity.get('id')
    role = identity.get('role')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM interviews WHERE id = ?", (interview_id,))
    interview = cursor.fetchone()
    conn.close()
    
    if not interview:
        return jsonify({"message": "Interview not found"}), 404
        
    if interview['user_id'] != user_id and role != 'admin':
        return jsonify({"message": "Unauthorized access to report"}), 403
        
    pdf_filename = f"report_{interview_id}.pdf"
    pdf_path = os.path.join(Config.UPLOAD_FOLDER, pdf_filename)
    
    if not os.path.exists(pdf_path):
        # Re-generate if missing
        try:
            generate_pdf_report(Config.DATABASE, interview_id, pdf_path)
        except Exception as e:
            return jsonify({"message": f"Failed to generate report: {str(e)}"}), 500
            
    return send_file(pdf_path, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')
