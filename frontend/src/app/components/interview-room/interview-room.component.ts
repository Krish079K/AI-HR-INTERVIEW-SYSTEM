import { Component, OnInit, OnDestroy, ViewChild, ElementRef, inject, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { InterviewService } from '../../services/interview.service';

// Declarations for Web Speech API (for TypeScript compilation)
declare var webkitSpeechRecognition: any;
declare var SpeechRecognition: any;



@Component({
  selector: 'app-interview-room',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './interview-room.component.html',
  styleUrls: ['./interview-room.component.css']
})
export class InterviewRoomComponent implements OnInit, OnDestroy {
  private interviewService = inject(InterviewService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private ngZone = inject(NgZone);

  @ViewChild('videoElement') videoElement!: ElementRef<HTMLVideoElement>;
  @ViewChild('canvasElement') canvasElement!: ElementRef<HTMLCanvasElement>;

  category = '';
  interviewId!: number;
  questions: any[] = [];
  currentQuestionIndex = 0;
  
  // App States
  // 'loading', 'ready', 'speaking', 'listening', 'processing', 'completed'
  roomState: 'loading' | 'ready' | 'speaking' | 'listening' | 'processing' | 'completed' = 'loading';
  
  // Timer
  timerValue = 60;
  private timerInterval: any;

  // Media Streams & Recording
  mediaStream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];

  // Web Speech API
  private recognition: any = null;
  liveTranscript = '';
  finalTranscriptForQuestion = '';
  speechRecognitionFailed = false;

  // Periodic Face Analysis Telemetry
  private frameAnalysisInterval: any;
  currentEmotion = 'Detecting...';
  eyeContactStatus = 'Detecting...';
  eyeContactScoreSum = 0;
  frameAnalysisCount = 0;
  accumulatedEmotions: { [key: string]: number } = {};

  // Audio Visualizer Waveform Variables
  audioContext: AudioContext | null = null;
  analyser: AnalyserNode | null = null;
  microphoneStream: MediaStreamAudioSourceNode | null = null;
  animationFrameId: number | null = null;
  waveBars: number[] = Array(20).fill(5);

  ngOnInit() {
    this.category = this.route.snapshot.paramMap.get('category') || 'HR';
    const sessionId = this.route.snapshot.queryParamMap.get('session');
    if (sessionId) {
      this.interviewId = parseInt(sessionId);
    } else {
      this.router.navigate(['/dashboard']);
      return;
    }

    this.loadQuestions();
  }

  ngOnDestroy() {
    this.stopAllMedia();
    this.stopTimer();
  }

  loadQuestions() {
    this.interviewService.getQuestions(this.category).subscribe({
      next: (data) => {
        this.questions = data;
        if (this.questions.length > 0) {
          this.setupWebcam();
        } else {
          alert("No questions found for this category.");
          this.router.navigate(['/dashboard']);
        }
      },
      error: (err) => {
        console.error("Failed to load questions:", err);
        this.router.navigate(['/dashboard']);
      }
    });
  }

  setupWebcam() {
    navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: true })
      .then(stream => {
        this.mediaStream = stream;
        
        // Log audio track diagnostics
        try {
          const audioTracks = stream.getAudioTracks();
          console.log("Speech Diagnostics - Audio tracks resolved:", audioTracks.map(t => ({
            label: t.label,
            enabled: t.enabled,
            readyState: t.readyState
          })));
        } catch (e) {
          console.warn("Speech Diagnostics - Failed to inspect audio tracks:", e);
        }

        if (this.videoElement) {
          this.videoElement.nativeElement.srcObject = stream;
        }
        this.roomState = 'ready';
        this.setupAudioVisualizer(stream);
      })
      .catch(err => {
        console.error("Camera access denied:", err);
        alert("Camera and Microphone access are required to run the interview simulation.");
        this.router.navigate(['/dashboard']);
      });
  }

  setupAudioVisualizer(stream: MediaStream) {
    try {
      this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 64;
      const bufferLength = this.analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      // Separate audio-only track for the visualizer
      const audioTrack = new MediaStream(stream.getAudioTracks());
      this.microphoneStream = this.audioContext.createMediaStreamSource(audioTrack);
      this.microphoneStream.connect(this.analyser);
      
      const updateWave = () => {
        if (!this.analyser) return;
        this.analyser.getByteFrequencyData(dataArray);
        
        // Map frequency data to 20 visual bars
        for (let i = 0; i < 20; i++) {
          const val = dataArray[i % bufferLength];
          // Scale to max height of 60px
          this.waveBars[i] = Math.max(5, (val / 255) * 60);
        }
        this.animationFrameId = requestAnimationFrame(updateWave);
      };
      
      updateWave();
    } catch (e) {
      console.warn("Audio Visualizer API not supported in this browser:", e);
    }
  }

  startInterviewSession() {
    this.currentQuestionIndex = 0;
    this.askCurrentQuestion();
  }

  askCurrentQuestion() {
    this.roomState = 'speaking';
    this.liveTranscript = '';
    this.finalTranscriptForQuestion = '';
    
    const questionText = this.questions[this.currentQuestionIndex].question_text;
    
    // Web Speech API - Text to Speech (TTS)
    const utterance = new SpeechSynthesisUtterance(questionText);
    
    // Choose an English voice if available
    const voices = window.speechSynthesis.getVoices();
    const enVoice = voices.find(v => v.lang.startsWith('en'));
    if (enVoice) {
      utterance.voice = enVoice;
    }
    
    utterance.onend = () => {
      this.startListening();
    };
    
    utterance.onerror = (e) => {
      console.error("TTS synthesis error:", e);
      // Fallback: start listening immediately
      this.startListening();
    };

    window.speechSynthesis.speak(utterance);
  }

  startListening() {
    this.roomState = 'listening';
    this.timerValue = 60;
    this.audioChunks = [];
    
    // 1. Initialize audio recording
    if (this.mediaStream) {
      // Use standard constraints for audio recording (MIME standard WAV/WebM)
      const options = { mimeType: 'audio/webm' };
      try {
        this.mediaRecorder = new MediaRecorder(this.mediaStream, options);
      } catch (e) {
        // Fallback mime type
        this.mediaRecorder = new MediaRecorder(this.mediaStream);
      }

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        this.sendAnswerToBackend(audioBlob);
      };

      this.mediaRecorder.start();
    }

    // 2. Initialize and Start Web Speech Recognition (Speech to Text) for this question
    this.stopSpeechRecognition(); // Ensure duplicate or old instance is cleaned up

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRec) {
      this.speechRecognitionFailed = false;
      this.recognition = new SpeechRec();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';

      this.recognition.onresult = (event: any) => {
        this.ngZone.run(() => {
          if (this.roomState !== 'listening') return;
          
          let finalTranscript = '';
          let interimTranscript = '';
          for (let i = 0; i < event.results.length; ++i) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              finalTranscript += transcript + ' ';
            } else {
              interimTranscript += transcript;
            }
          }
          const text = (finalTranscript + interimTranscript).trim();
          console.log("Transcript received:", text);
          this.finalTranscriptForQuestion = finalTranscript.trim();
          this.liveTranscript = text;
        });
      };

      this.recognition.onerror = (err: any) => {
        this.ngZone.run(() => {
          console.error("SpeechRecognition error:", err.error || err);
          const errType = err.error;
          if (errType === 'no-speech' || errType === 'network') {
            console.log(`SpeechRecognition: Auto-restarting due to ${errType} error...`);
          } else {
            this.speechRecognitionFailed = true;
            if (errType === 'not-allowed') {
              this.liveTranscript = "[Microphone permission denied. Please type your response below.]";
            } else if (errType === 'audio-capture') {
              this.liveTranscript = "[Audio capture failed. Please type your response below.]";
            } else {
              this.liveTranscript = `[Speech recognition failed: ${errType}. Please type your response below.]`;
            }
          }
        });
      };

      const currentRec = this.recognition;
      this.recognition.onend = () => {
        this.ngZone.run(() => {
          if (this.roomState === 'listening' && this.recognition === currentRec) {
            console.log("Recognition restarted");
            try {
              currentRec.start();
            } catch (e) {
              console.warn("Failed to auto-restart speech recognition:", e);
            }
          }
        });
      };

      try {
        this.recognition.start();
        console.log(`Recognition started for question ${this.currentQuestionIndex + 1}`);
      } catch (e) {
        console.error("Failed to start speech recognition:", e);
      }
    } else {
      this.speechRecognitionFailed = true;
      this.liveTranscript = "[Speech Recognition API not supported in this browser. Please use Google Chrome.]";
    }

    // 3. Start Live Camera telemetry ticks
    this.eyeContactScoreSum = 0;
    this.frameAnalysisCount = 0;
    this.accumulatedEmotions = {};
    
    this.frameAnalysisInterval = setInterval(() => {
      this.captureAndAnalyzeFrame();
    }, 1500); // Check frame every 1.5 seconds

    // 4. Start Countdown Timer
    this.timerInterval = setInterval(() => {
      this.timerValue--;
      if (this.timerValue <= 0) {
        this.submitAnswer();
      }
    }, 1000);
  }

  captureAndAnalyzeFrame() {
    if (!this.videoElement || !this.canvasElement) return;
    
    const video = this.videoElement.nativeElement;
    const canvas = this.canvasElement.nativeElement;
    const ctx = canvas.getContext('2d');
    
    if (ctx && video.readyState === video.HAVE_ENOUGH_DATA) {
      // Draw frame to hidden canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const base64Image = canvas.toDataURL('image/jpeg', 0.6); // Compress to 60% quality to optimize payload size
      
      this.interviewService.submitFrame(this.interviewId, base64Image).subscribe({
        next: (res) => {
          if (res.face_detected) {
            this.currentEmotion = res.dominant_emotion;
            this.eyeContactStatus = res.eye_contact;
            
            // Accumulate statistics for final session grading
            this.eyeContactScoreSum += res.eye_contact_score;
            this.frameAnalysisCount++;
            
            const emo = res.dominant_emotion;
            this.accumulatedEmotions[emo] = (this.accumulatedEmotions[emo] || 0) + 1;
          } else {
            this.currentEmotion = 'Absent';
            this.eyeContactStatus = 'Absent';
          }
        },
        error: (err) => {
          console.warn("Frame analysis telemetry error:", err);
        }
      });
    }
  }

  submitAnswer() {
    this.roomState = 'processing';
    this.stopTimer();

    // Stop live camera tick
    if (this.frameAnalysisInterval) {
      clearInterval(this.frameAnalysisInterval);
    }

    // Stop browser speech engine
    this.stopSpeechRecognition();

    // Stop mic recording which triggers mediaRecorder.onstop() callback -> sendAnswerToBackend()
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    } else {
      // No active recording (fallback if stream was interrupted)
      this.sendAnswerToBackend(null);
    }
  }

  stopSpeechRecognition() {
    if (this.recognition) {
      try {
        this.recognition.onend = null; // Clear onend listener to prevent auto-restart when we intentionally stop it
        this.recognition.abort();      // Discards any active session immediately
        console.log("SpeechRecognition stopped/aborted.");
      } catch (e) {
        console.warn("Error stopping speech recognition:", e);
      }
      this.recognition = null;
    }
  }

  enableManualInput() {
    this.speechRecognitionFailed = true;
    this.stopSpeechRecognition();
    console.log("Manual input fallback enabled by user.");
  }

  sendAnswerToBackend(audioBlob: Blob | null) {
    const questionId = this.questions[this.currentQuestionIndex].id;
    
    // Calculate accumulated telemetry values
    const avgEyeContact = this.frameAnalysisCount > 0 
      ? Math.round(this.eyeContactScoreSum / this.frameAnalysisCount) 
      : 85; // moderate default if no frames processed

    // Compute relative emotion distribution
    const emotionsList: { emotion: string; count: number }[] = [];
    Object.keys(this.accumulatedEmotions).forEach(key => {
      emotionsList.push({ emotion: key, count: this.accumulatedEmotions[key] });
    });
    const emotionsJson = JSON.stringify(emotionsList);

    // Call submit answer
    this.interviewService.submitAnswer(
      this.interviewId, 
      questionId, 
      audioBlob, 
      this.liveTranscript.trim() || this.finalTranscriptForQuestion.trim(), 
      avgEyeContact, 
      emotionsJson
    ).subscribe({
      next: (res) => {
        // Move to next question or complete
        this.currentQuestionIndex++;
        if (this.currentQuestionIndex < this.questions.length) {
          this.askCurrentQuestion();
        } else {
          this.completeInterviewSession();
        }
      },
      error: (err) => {
        console.error("Failed to submit question answer:", err);
        alert("Failed to submit answer. Skipping to next question.");
        this.currentQuestionIndex++;
        if (this.currentQuestionIndex < this.questions.length) {
          this.askCurrentQuestion();
        } else {
          this.completeInterviewSession();
        }
      }
    });
  }

  completeInterviewSession() {
    this.roomState = 'completed';
    this.interviewService.completeInterview(this.interviewId).subscribe({
      next: (res) => {
        this.stopAllMedia();
        // Redirect to result page
        this.router.navigate(['/result', this.interviewId]);
      },
      error: (err) => {
        console.error("Failed to complete interview session:", err);
        alert("Assessment processed with errors. Navigating to results dashboard.");
        this.router.navigate(['/result', this.interviewId]);
      }
    });
  }

  stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
    }
  }

  stopAllMedia() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }
    if (this.frameAnalysisInterval) {
      clearInterval(this.frameAnalysisInterval);
    }
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    if (this.audioContext) {
      this.audioContext.close();
    }
    this.stopSpeechRecognition();
  }
}
