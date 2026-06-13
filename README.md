# AI Virtual HR Interviewer

An AI-powered full-stack mock HR interview simulator. The application utilizes computer vision (OpenCV) and deep learning (DeepFace) to evaluate facial expressions and eye contact, combined with speech-to-text (SpeechRecognition) and natural language processing (spaCy & NLTK) to analyze candidates' vocal pacing, transcription, and technical keyword alignment. At the end of the interview, a detailed report is rendered alongside a downloadable HR-grade PDF feedback report.

---

## Key Features

1. **Candidate Profile & Dashboard**: Register accounts, select interview types (HR, Technical, Behavioral), check aggregate metrics, and view chronological interview history.
2. **Interactive AI Interviewer Room**: Real-time webcam viewport with overlay face boxes, microphone status bar, circular timer count down, and live telemetry tracking.
3. **AI Video Analysis**: Estimates eye contact maintenance from pupils coordinate tracking and classifies 7 micro-emotions frame-by-frame.
4. **AI Speech Analysis**: Evaluates speaking rates (WPM), voice standard deviation energy, and computes cosine similarity against ideal model answers.
5. **Interactive Graphics**: Compiles results into a radar competency vector and emotion distribution doughnut chart using Chart.js.
6. **HR Report Generator**: Compiles assessment summaries and question critiques into a professional PDF using ReportLab.
7. **Admin Control Console**: Manage the platform question library, inspect system-wide analytics, and view candidates' list.

---

## Project Structure

```
AI INTERVIEW/
├── backend/
│   ├── app.py                     # Flask Main Server Entry point
│   ├── config.py                  # Global Flask configuration settings
│   ├── database.py                # Database helper (schema creation & seeding)
│   ├── requirements.txt           # Python dependency declarations
│   ├── routes/
│   │   ├── auth.py                # Registration and login blueprint APIs
│   │   ├── interviews.py          # Session and submission analysis APIs
│   │   └── admin.py               # CRUD questions and platform stats APIs
│   └── services/
│       ├── face_analysis.py       # OpenCV Haar cascades & DeepFace emotion analyzer
│       ├── speech_analysis.py     # SpeechRecognition, spaCy, & NLTK keyword scorer
│       └── report_generator.py    # ReportLab PDF compiler
├── frontend/                      # Angular 17+ Standalone project
│   ├── package.json
│   ├── angular.json
│   └── src/
│       ├── main.ts
│       ├── styles.css             # Global dark-cyber-theme stylesheet
│       └── app/
│           ├── app.config.ts
│           ├── app.routes.ts      # Client-side router mappings
│           ├── components/
│           │   ├── landing/       # Futuristic landing page
│           │   ├── auth/          # Shared Sign In & Sign Up tabbed sliding page
│           │   ├── dashboard/     # Cockpit with metrics and category launch buttons
│           │   ├── interview-room/# Live camera room with Web Speech TTS/STT and gauges
│           │   ├── result-analysis/# Chart.js analytics dashboard
│           │   └── admin/         # CRUD question library & candidates table
│           ├── guards/            # Functional authGuard and loginGuard
│           └── services/          # AuthService, InterviewService, AdminService
└── README.md
```

---

## Setup & Running Instructions

### 1. Prerequisites
Ensure you have the following installed on your machine:
* Python 3.10+ (Standard Python is pre-installed)
* Node.js v18+ & npm (Installed during backend preparation)

---

### 2. Backend Installation (Python Flask)

1. Open a command prompt inside the `backend/` directory.
2. Create a Python Virtual Environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   * **Windows Command Prompt**:
     ```cmd
     venv\Scripts\activate.bat
     ```
   * **Windows PowerShell**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   * **Linux/macOS**:
     ```bash
     source venv/bin/activate
     ```
4. Install the dependencies listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
5. Install the spaCy NLP small English language model:
   ```bash
   python -m spacy download en_core_web_sm
   ```
6. Run the Flask application:
   ```bash
   python app.py
   ```
The Flask API server will start on `http://localhost:5000`. It will automatically check for and initialize the SQLite database `interviewer.db` and seed it with default questions and a master administrator user account.

* **Admin Username**: `admin@interview.ai`
* **Admin Password**: `admin123`

---

### 3. Frontend Installation (Angular 17)

1. Open a new terminal inside the `frontend/` directory.
2. Install the package dependencies (which includes `@angular/cli`, `chart.js`, etc.):
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run start
   ```
4. Open your browser and navigate to `http://localhost:4200`.

---

## Key Technical Decisions

* **Base64 Frame Grabs (Telemetry)**: To prevent large video file uploads and improve latency, the client encodes webcam canvas frames to base64 and uploads them to `/frame` every 1.5 seconds. OpenCV Haar Cascades track the face and pupil coordinates locally on the server, while DeepFace registers facial expressions.
* **Hybrid Speech Recognition**: Uses the browser's Web Speech API (`webkitSpeechRecognition`) for real-time transcription on the screen, and sends this text along with the audio file. The backend saves the WAV file and attempts transcription via Python's `SpeechRecognition` library. If any decoder issues or rate limits occur, it falls back to the browser-generated transcript, ensuring 100% processing stability.
* **Database Seeding**: Checks for table states and pre-populates a library of 12 detailed mock interview questions (across HR, Technical, and Behavioral) and a default administrator user account.
* **ReportLab Custom Canvas**: Overrides page drawing loops to compute overall page totals (e.g., "Page 1 of 3") and renders modern grid structures for corporate reporting.
