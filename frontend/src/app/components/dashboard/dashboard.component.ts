import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { InterviewService } from '../../services/interview.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {
  authService = inject(AuthService);
  private interviewService = inject(InterviewService);
  private router = inject(Router);

  userName = '';
  history: any[] = [];
  stats = {
    totalInterviews: 0,
    avgScore: 0,
    technicalAvg: 0,
    communicationAvg: 0
  };
  
  loading = true;

  ngOnInit() {
    const user = this.authService.getUser();
    if (user) {
      this.userName = user.name;
    }
    this.loadHistory();
  }

  loadHistory() {
    this.interviewService.getHistory().subscribe({
      next: (data) => {
        this.history = data;
        this.calculateStats();
        this.loading = false;
      },
      error: (err) => {
        console.error("Failed to load interview history:", err);
        this.loading = false;
      }
    });
  }

  calculateStats() {
    if (this.history.length === 0) return;
    
    this.stats.totalInterviews = this.history.length;
    
    let sumScore = 0;
    let sumTech = 0;
    let sumComm = 0;
    
    this.history.forEach(item => {
      sumScore += item.overall_score || 0;
      sumTech += item.technical_score || 0;
      sumComm += item.communication_score || 0;
    });
    
    this.stats.avgScore = Math.round(sumScore / this.history.length);
    this.stats.technicalAvg = Math.round(sumTech / this.history.length);
    this.stats.communicationAvg = Math.round(sumComm / this.history.length);
  }

  startInterview(category: string) {
    this.interviewService.startInterview(category).subscribe({
      next: (res) => {
        // Navigate to the interview room passing the session ID and category
        this.router.navigate(['/interview-room', category], { 
          queryParams: { session: res.interview_id } 
        });
      },
      error: (err) => {
        alert(err.error?.message || "Failed to start interview session.");
      }
    });
  }

  downloadReport(interviewId: number) {
    this.interviewService.downloadReport(interviewId).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `AI_HR_Report_${interviewId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        console.error("Failed to download PDF report:", err);
        alert("Could not retrieve PDF report.");
      }
    });
  }
}
