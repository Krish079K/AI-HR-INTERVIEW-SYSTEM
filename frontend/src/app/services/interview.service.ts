import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class InterviewService {
  private http = inject(HttpClient);
  
  get apiUrl(): string {
    const customUrl = localStorage.getItem('customApiUrl');
    return `${customUrl || environment.apiUrl}/interviews`;
  }

  getQuestions(category: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/questions?category=${category}`);
  }

  startInterview(category: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/start`, { category });
  }

  submitFrame(interviewId: number, base64Image: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/${interviewId}/frame`, { image: base64Image });
  }

  submitAnswer(
    interviewId: number, 
    questionId: number, 
    audioBlob: Blob | null, 
    transcript: string,
    eyeContactRatio: number,
    emotionsJson: string
  ): Observable<any> {
    const formData = new FormData();
    if (audioBlob) {
      formData.append('audio', audioBlob, 'response.wav');
    }
    formData.append('transcript', transcript);
    formData.append('eye_contact_ratio', eyeContactRatio.toString());
    formData.append('emotions', emotionsJson);

    return this.http.post<any>(
      `${this.apiUrl}/${interviewId}/question/${questionId}/answer`, 
      formData
    );
  }

  completeInterview(interviewId: number): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/${interviewId}/complete`, {});
  }

  getHistory(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/history`);
  }

  getResult(interviewId: number): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/${interviewId}/result`);
  }

  downloadReport(interviewId: number): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${interviewId}/report`, {
      responseType: 'blob'
    });
  }
}
