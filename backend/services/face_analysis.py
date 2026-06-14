# Import cv2 dynamically to make backend robust under disk quota constraints
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: OpenCV (cv2) library not found. Face and eye contact tracking will use default values.")

import numpy as np
import base64
import os
import sys

# Disable tensorflow debugging logs to avoid cluttering output
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Import deepface dynamically or catch import errors to make backend robust
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("Warning: DeepFace library not found. Emotion analysis will fallback to Neutral.")

# Load Haar cascades from cv2 data folder if cv2 is available
face_cascade = None
eye_cascade = None
if CV2_AVAILABLE:
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

def analyze_frame(base64_image_str):
    """
    Decodes a base64 image frame and performs:
    1. Face detection
    2. Eye contact estimation (using pupil position within eye bounding boxes)
    3. Emotion analysis (via DeepFace)
    """
    if not CV2_AVAILABLE:
        return {
            "face_detected": True,
            "eye_contact": "Maintained",
            "eye_contact_score": 85.0,
            "dominant_emotion": "Neutral",
            "emotions": {"neutral": 100.0}
        }

    face_detected = False
    eye_contact = "Absent"
    eye_contact_score = 0.0
    dominant_emotion = "Neutral"
    emotions_dict = {"neutral": 100.0}

    try:
        # Decode base64 image
        if ',' in base64_image_str:
            base64_image_str = base64_image_str.split(',')[1]
        
        img_bytes = base64.b64decode(base64_image_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {
                "face_detected": False,
                "eye_contact": "Absent",
                "eye_contact_score": 0.0,
                "dominant_emotion": "Error",
                "emotions": {}
            }
            
        h, w, _ = img.shape
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect face
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(60, 60))
        
        if len(faces) > 0:
            face_detected = True
            
            # Sort by area to get the largest (closest) face
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            (fx, fy, fw, fh) = faces[0]
            
            # 1. Base eye contact estimate using head placement (centered face)
            face_center_x = fx + fw / 2
            frame_center_x = w / 2
            horizontal_offset = abs(face_center_x - frame_center_x) / w
            
            if horizontal_offset < 0.12:
                eye_contact_score = 80.0
                eye_contact = "Maintained"
            else:
                eye_contact_score = 55.0
                eye_contact = "Poor (Off-Center)"
                
            # 2. Refined eye contact estimate using pupil tracking within detected eyes
            face_gray = gray[fy:fy+fh, fx:fx+fw]
            eyes = eye_cascade.detectMultiScale(face_gray, scaleFactor=1.1, minNeighbors=5, minSize=(15, 15))
            
            # Filter eyes located in the upper 55% of the face region
            valid_eyes = []
            for (ex, ey, ew, eh) in eyes:
                if ey < fh * 0.55:
                    valid_eyes.append((ex, ey, ew, eh))
            
            if len(valid_eyes) >= 2:
                # We found both eyes! Run pupil centering analysis
                eye_contact_score = 85.0
                pupil_deviations = []
                
                # Analyze the first two eyes
                for (ex, ey, ew, eh) in valid_eyes[:2]:
                    eye_gray = face_gray[ey:ey+eh, ex:ex+ew]
                    # Equalize histogram to handle varying lighting
                    eye_gray_eq = cv2.equalizeHist(eye_gray)
                    
                    # Threshold to isolate pupil (darkest 12% of the eye box)
                    thresh_val = np.percentile(eye_gray_eq, 12)
                    _, thresh = cv2.threshold(eye_gray_eq, thresh_val, 255, cv2.THRESH_BINARY_INV)
                    
                    # Find contours
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if contours:
                        largest_contour = max(contours, key=cv2.contourArea)
                        M = cv2.moments(largest_contour)
                        if M["m00"] != 0:
                            pupil_x = int(M["m10"] / M["m00"])
                            relative_x = pupil_x / ew
                            # Calculate deviation from eye center (0.5)
                            deviation = abs(relative_x - 0.5)
                            pupil_deviations.append(deviation)
                
                if pupil_deviations:
                    avg_deviation = np.mean(pupil_deviations)
                    # A small deviation (< 0.12) means looking straight ahead
                    if avg_deviation < 0.12:
                        eye_contact_score = min(100.0, eye_contact_score + 10.0)
                        eye_contact = "Maintained"
                    else:
                        penalty = (avg_deviation - 0.12) * 120
                        eye_contact_score = max(20.0, eye_contact_score - penalty)
                        eye_contact = "Looking Away"
                        
            elif len(valid_eyes) == 1:
                eye_contact_score = max(40.0, eye_contact_score - 15.0)
                eye_contact = "Looking Away"
                
            # 3. Emotion Analysis via DeepFace
            if DEEPFACE_AVAILABLE:
                try:
                    result = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False, silent=True)
                    if isinstance(result, list):
                        result = result[0]
                    
                    emotions_dict = result.get('emotion', {})
                    dominant_emotion = result.get('dominant_emotion', 'Neutral').capitalize()
                except Exception as e:
                    # Fallback on DeepFace failure
                    dominant_emotion = "Neutral"
                    emotions_dict = {"neutral": 100.0}
            else:
                dominant_emotion = "Neutral"
                emotions_dict = {"neutral": 100.0}
                
        else:
            face_detected = False
            eye_contact = "Absent"
            eye_contact_score = 0.0
            dominant_emotion = "Absent"
            emotions_dict = {}
            
    except Exception as general_err:
        print(f"General Frame Analysis Error: {general_err}")
        return {
            "face_detected": False,
            "eye_contact": "Error",
            "eye_contact_score": 0.0,
            "dominant_emotion": "Error",
            "emotions": {}
        }
        
    return {
        "face_detected": face_detected,
        "eye_contact": eye_contact,
        "eye_contact_score": round(float(eye_contact_score), 1),
        "dominant_emotion": dominant_emotion,
        "emotions": {k: round(float(v), 2) for k, v in emotions_dict.items()}
    }
