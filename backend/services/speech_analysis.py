import os
import wave
import numpy as np
import speech_recognition as sr
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Load spaCy dynamically
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("Warning: spaCy library not found. Lemmatization will fall back.")

# Load scikit-learn dynamically
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn library not found. Cosine similarity will fall back.")

# Ensure NLTK data is downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    try:
        nltk.download('punkt', quiet=True)
    except Exception as e:
        print(f"Warning: Failed to download NLTK tokenizers/punkt: {e}")
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    try:
        nltk.download('stopwords', quiet=True)
    except Exception as e:
        print(f"Warning: Failed to download NLTK corpora/stopwords: {e}")

def safe_word_tokenize(text):
    try:
        return word_tokenize(text)
    except Exception as e:
        print(f"Warning: NLTK word_tokenize failed: {e}. Using regex fallback.")
        import re
        return re.findall(r'\w+|[^\w\s]', text)

def safe_get_stopwords():
    try:
        return set(stopwords.words('english'))
    except Exception as e:
        print(f"Warning: NLTK stopwords failed: {e}. Using default set fallback.")
        return {
            "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
            "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
            "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
            "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
            "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
            "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
            "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
            "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
            "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
            "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
            "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
            "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"
        }

# Load spaCy model
nlp = None
if SPACY_AVAILABLE:
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError:
        # Fallback to small model if medium isn't installed
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = None
            print("Warning: spaCy model not found. Semantic similarity will fall back to TF-IDF.")

def get_audio_duration_and_amplitude(audio_path):
    """
    Reads a WAV file and returns its duration (in seconds) 
    and average amplitude variation (for voice energy analysis).
    """
    try:
        with wave.open(audio_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate)
            
            # Read frames to analyze energy (amplitude)
            raw_data = wav_file.readframes(frames)
            audio_data = np.frombuffer(raw_data, dtype=np.int16)
            
            if len(audio_data) > 0:
                # Normalize and find RMS (Root Mean Square) energy
                rms = np.sqrt(np.mean(audio_data.astype(float)**2))
                # Measure variance to detect monotone vs expressive voice
                std_dev = np.std(audio_data)
            else:
                rms = 0
                std_dev = 0
                
            return duration, float(rms), float(std_dev)
    except Exception as e:
        print(f"Error reading audio file properties: {e}")
        # Default fallback
        return 10.0, 1000.0, 500.0

def transcribe_audio(audio_path):
    """
    Transcribes a WAV file using the SpeechRecognition library.
    """
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            # Use Google Speech Recognition API (free tier)
            text = recognizer.recognize_google(audio_data)
            return text, None
    except sr.UnknownValueError:
        return "", "Speech was unclear or background noise was too high."
    except sr.RequestError as e:
        return "", f"Speech recognition service error: {str(e)}"
    except Exception as e:
        return "", f"Transcription error: {str(e)}"

def analyze_speech_content(transcript, target_keywords, ideal_answer=None):
    """
    Computes NLP metrics:
    1. Keyword matching: percentage of keywords found in transcript (lemmatized).
    2. Semantic similarity: Cosine similarity between transcript and ideal answer.
    """
    if not transcript:
        return {
            "matched_keywords": [],
            "keyword_score": 0.0,
            "semantic_similarity": 0.0,
            "matched_count": 0,
            "total_keywords": 0
        }
        
    # Standardize transcript
    transcript_lower = transcript.lower()
    
    # 1. Keyword Matching (using NLTK tokenization & lemmatization if possible)
    keywords_list = [k.strip().lower() for k in target_keywords.split(',') if k.strip()]
    matched_keywords = []
    
    # Simple check and lemmatization match
    tokens = safe_word_tokenize(transcript_lower)
    stop_words = safe_get_stopwords()
    filtered_tokens = [w for w in tokens if w.isalnum() and w not in stop_words]
    
    # Parse with spacy if available for better lemmatization
    if nlp:
        doc = nlp(transcript_lower)
        lemmatized_tokens = [token.lemma_ for token in doc]
        
        for kw in keywords_list:
            kw_doc = nlp(kw)
            kw_lemma = kw_doc[0].lemma_ if len(kw_doc) > 0 else kw
            if kw in transcript_lower or kw_lemma in lemmatized_tokens:
                matched_keywords.append(kw)
    else:
        # Fallback to simple substring match
        for kw in keywords_list:
            if kw in transcript_lower:
                matched_keywords.append(kw)
                
    keyword_score = (len(matched_keywords) / len(keywords_list) * 100.0) if keywords_list else 0.0
    
    # 2. Semantic Similarity to Ideal Answer
    similarity_score = 0.0
    if ideal_answer:
        if nlp:
            # Use spaCy word vectors (en_core_web_md)
            doc_user = nlp(transcript_lower)
            doc_ideal = nlp(ideal_answer.lower())
            if doc_user.vector_norm and doc_ideal.vector_norm:
                similarity_score = doc_user.similarity(doc_ideal) * 100.0
        else:
            # Fallback to TF-IDF Cosine Similarity if sklearn is available, otherwise use simple word overlap
            try:
                if SKLEARN_AVAILABLE:
                    vectorizer = TfidfVectorizer()
                    tfidf = vectorizer.fit_transform([transcript_lower, ideal_answer.lower()])
                    similarity_score = (tfidf * tfidf.T).A[0, 1] * 100.0
                else:
                    # Simple word overlap similarity fallback
                    user_words = set(transcript_lower.split())
                    ideal_words = set(ideal_answer.lower().split())
                    if not ideal_words:
                        similarity_score = 100.0
                    else:
                        overlap = len(user_words.intersection(ideal_words))
                        similarity_score = (overlap / len(ideal_words)) * 100.0
            except Exception as e:
                print(f"Similarity calculation error: {e}")
                similarity_score = 50.0 # moderate baseline fallback
                
    return {
        "matched_keywords": matched_keywords,
        "keyword_score": round(keyword_score, 1),
        "semantic_similarity": round(similarity_score, 1),
        "matched_count": len(matched_keywords),
        "total_keywords": len(keywords_list)
    }

def analyze_communication(transcript, duration, rms, std_dev):
    """
    Analyzes communication quality:
    1. Speaking Speed (WPM): ideal is 120-150.
    2. Voice Expression/Energy (via amplitude variation standard deviation).
    3. Communication Quality Score.
    """
    if not transcript or duration <= 0:
        return {
            "wpm": 0.0,
            "speaking_speed_status": "Silent",
            "voice_energy": "Monotone",
            "communication_score": 0.0,
            "confidence_score": 0.0
        }
        
    words = [w for w in safe_word_tokenize(transcript) if w.isalnum()]
    word_count = len(words)
    
    # Calculate WPM
    wpm = (word_count / duration) * 60.0
    
    # Evaluate Speaking Speed
    if wpm < 80:
        speed_status = "Too Slow"
        speed_score = 50.0
    elif 80 <= wpm < 110:
        speed_status = "Normal (Paced)"
        speed_score = 80.0
    elif 110 <= wpm <= 150:
        speed_status = "Fluent (Ideal)"
        speed_score = 100.0
    elif 150 < wpm <= 180:
        speed_status = "Fast (Good)"
        speed_score = 85.0
    else:
        speed_status = "Too Fast"
        speed_score = 40.0
        
    # Evaluate Voice Expression / Vocal Confidence (std_dev of amplitude)
    # Highly monotone voices have low std_dev; natural speaking has higher standard deviation.
    # We calibrate these values for standard 16-bit PCM wav files.
    if std_dev < 100:
        voice_energy = "Very Quiet / Whisper"
        voice_score = 30.0
    elif 100 <= std_dev < 800:
        voice_energy = "Soft / Monotone"
        voice_score = 65.0
    elif 800 <= std_dev <= 4000:
        voice_energy = "Dynamic & Confident"
        voice_score = 95.0
    else:
        voice_energy = "Loud / High Pitch"
        voice_score = 75.0
        
    # Calculate communication metrics
    comm_score = (speed_score * 0.6) + (min(100.0, word_count * 2) * 0.4) # penalty for extremely short answers
    vocal_confidence_score = (speed_score * 0.5) + (voice_score * 0.5)
    
    return {
        "wpm": round(wpm, 1),
        "speaking_speed_status": speed_status,
        "voice_energy": voice_energy,
        "communication_score": round(comm_score, 1),
        "confidence_score": round(vocal_confidence_score, 1)
    }
