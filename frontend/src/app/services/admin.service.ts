import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private http = inject(HttpClient);
  
  get apiUrl(): string {
    const customUrl = localStorage.getItem('customApiUrl');
    return `${customUrl || environment.apiUrl}/admin`;
  }

  getQuestions(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/questions`);
  }

  createQuestion(question: { category: string; question_text: string; keywords: string; ideal_answer?: string }): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/questions`, question);
  }

  updateQuestion(id: number, question: { category: string; question_text: string; keywords: string; ideal_answer?: string }): Observable<any> {
    return this.http.put<any>(`${this.apiUrl}/questions/${id}`, question);
  }

  deleteQuestion(id: number): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/questions/${id}`);
  }

  getStats(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/stats`);
  }

  getCandidates(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/candidates`);
  }
}
