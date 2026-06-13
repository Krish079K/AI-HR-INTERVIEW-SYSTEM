import { Component, OnInit, AfterViewChecked, ElementRef, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { InterviewService } from '../../services/interview.service';
import { Chart } from 'chart.js/auto';

@Component({
  selector: 'app-result-analysis',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './result-analysis.component.html',
  styleUrls: ['./result-analysis.component.css']
})
export class ResultAnalysisComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private interviewService = inject(InterviewService);

  @ViewChild('radarCanvas') radarCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('doughnutCanvas') doughnutCanvas!: ElementRef<HTMLCanvasElement>;

  interviewId!: number;
  interviewData: any = null;
  responses: any[] = [];
  loading = true;

  // Chart instances
  private radarChart: any = null;
  private doughnutChart: any = null;

  ngOnInit() {
    this.interviewId = parseInt(this.route.snapshot.paramMap.get('id') || '0');
    if (!this.interviewId) {
      this.router.navigate(['/dashboard']);
      return;
    }
    this.loadResults();
  }

  loadResults() {
    this.interviewService.getResult(this.interviewId).subscribe({
      next: (data) => {
        this.interviewData = data.interview;
        this.responses = data.responses;
        this.loading = false;
        
        // Render charts after Angular renders the view elements
        setTimeout(() => {
          this.initCharts();
        }, 100);
      },
      error: (err) => {
        console.error("Failed to load interview results:", err);
        alert("Results not found or unauthorized.");
        this.router.navigate(['/dashboard']);
      }
    });
  }

  initCharts() {
    if (!this.interviewData) return;

    // Destroy existing charts to prevent memory leaks on re-renders
    if (this.radarChart) this.radarChart.destroy();
    if (this.doughnutChart) this.doughnutChart.destroy();

    // 1. Radar Chart: Competency Breakdown
    const radarCtx = this.radarCanvas.nativeElement.getContext('2d');
    if (radarCtx) {
      this.radarChart = new Chart(radarCtx, {
        type: 'radar',
        data: {
          labels: ['Technical', 'Communication', 'Confidence', 'Eye Contact'],
          datasets: [{
            label: 'Your Score (%)',
            data: [
              this.interviewData.technical_score,
              this.interviewData.communication_score,
              this.interviewData.confidence_score,
              this.interviewData.eye_contact_score
            ],
            backgroundColor: 'rgba(99, 102, 241, 0.2)',
            borderColor: '#6366f1',
            pointBackgroundColor: '#a855f7',
            pointBorderColor: '#fff',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false }
          },
          scales: {
            r: {
              angleLines: { color: 'rgba(255,255,255,0.08)' },
              grid: { color: 'rgba(255,255,255,0.08)' },
              pointLabels: { color: '#94a3b8', font: { size: 12, family: 'Outfit' } },
              ticks: { display: false, maxTicksLimit: 5 },
              min: 0,
              max: 100
            }
          }
        }
      });
    }

    // 2. Doughnut Chart: Emotion Distribution
    // Aggregate emotions from all question responses
    const emotionCounts: { [key: string]: number } = {};
    
    this.responses.forEach(r => {
      if (r.emotions && Array.isArray(r.emotions)) {
        r.emotions.forEach((e: any) => {
          const name = e.emotion || 'Neutral';
          emotionCounts[name] = (emotionCounts[name] || 0) + e.count;
        });
      }
    });

    // If no emotions logged, default to Neutral
    if (Object.keys(emotionCounts).length === 0) {
      emotionCounts['Neutral'] = 1;
    }

    const labels = Object.keys(emotionCounts);
    const counts = Object.values(emotionCounts);

    // Modern color mapping for emotions
    const emotionColors: { [key: string]: string } = {
      'Neutral': '#64748b',
      'Happy': '#10b981',
      'Sad': '#3b82f6',
      'Angry': '#ef4444',
      'Surprise': '#06b6d4',
      'Fear': '#a855f7',
      'Disgust': '#e11d48'
    };

    const bgColors = labels.map(lbl => emotionColors[lbl] || '#475569');

    const doughnutCtx = this.doughnutCanvas.nativeElement.getContext('2d');
    if (doughnutCtx) {
      this.doughnutChart = new Chart(doughnutCtx, {
        type: 'doughnut',
        data: {
          labels: labels,
          datasets: [{
            data: counts,
            backgroundColor: bgColors,
            borderColor: '#0f0d22',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#94a3b8', font: { family: 'Outfit', size: 12 } }
            }
          },
          cutout: '65%'
        }
      });
    }
  }

  downloadReport() {
    this.interviewService.downloadReport(this.interviewId).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `AI_HR_Report_${this.interviewId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        console.error("Failed to download PDF report:", err);
        alert("Failed to download report.");
      }
    });
  }
}
