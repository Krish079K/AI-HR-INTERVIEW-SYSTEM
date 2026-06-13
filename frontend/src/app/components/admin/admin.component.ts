import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { AdminService } from '../../services/admin.service';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterLink],
  templateUrl: './admin.component.html',
  styleUrls: ['./admin.component.css']
})
export class AdminComponent implements OnInit {
  authService = inject(AuthService);
  private adminService = inject(AdminService);
  private fb = inject(FormBuilder);

  // Stats & Candidate listings
  stats = {
    total_candidates: 0,
    total_interviews: 0,
    average_score: 0
  };
  candidates: any[] = [];
  questions: any[] = [];
  
  loadingStats = true;
  loadingCandidates = true;
  loadingQuestions = true;

  // Question Form states
  questionForm: FormGroup = this.fb.group({
    category: ['HR', Validators.required],
    question_text: ['', [Validators.required, Validators.minLength(10)]],
    keywords: ['', Validators.required],
    ideal_answer: ['']
  });

  isEditing = false;
  editingQuestionId: number | null = null;
  formErrorMessage: string | null = null;
  formSuccessMessage: string | null = null;

  ngOnInit() {
    this.loadStats();
    this.loadCandidates();
    this.loadQuestions();
  }

  loadStats() {
    this.adminService.getStats().subscribe({
      next: (data) => {
        this.stats = data;
        this.loadingStats = false;
      },
      error: (err) => {
        console.error("Failed to load admin stats:", err);
        this.loadingStats = false;
      }
    });
  }

  loadCandidates() {
    this.adminService.getCandidates().subscribe({
      next: (data) => {
        this.candidates = data;
        this.loadingCandidates = false;
      },
      error: (err) => {
        console.error("Failed to load candidates list:", err);
        this.loadingCandidates = false;
      }
    });
  }

  loadQuestions() {
    this.adminService.getQuestions().subscribe({
      next: (data) => {
        this.questions = data;
        this.loadingQuestions = false;
      },
      error: (err) => {
        console.error("Failed to load questions list:", err);
        this.loadingQuestions = false;
      }
    });
  }

  onSaveQuestion() {
    if (this.questionForm.invalid) {
      this.formErrorMessage = "Please fill in all required fields correctly.";
      return;
    }

    this.formErrorMessage = null;
    this.formSuccessMessage = null;
    const formData = this.questionForm.value;

    if (this.isEditing && this.editingQuestionId !== null) {
      this.adminService.updateQuestion(this.editingQuestionId, formData).subscribe({
        next: () => {
          this.formSuccessMessage = "Question updated successfully!";
          this.resetForm();
          this.loadQuestions();
          this.loadStats();
        },
        error: (err) => {
          this.formErrorMessage = err.error?.message || "Failed to update question.";
        }
      });
    } else {
      this.adminService.createQuestion(formData).subscribe({
        next: () => {
          this.formSuccessMessage = "Question created successfully!";
          this.resetForm();
          this.loadQuestions();
          this.loadStats();
        },
        error: (err) => {
          this.formErrorMessage = err.error?.message || "Failed to create question.";
        }
      });
    }
  }

  onEditQuestion(q: any) {
    this.isEditing = true;
    this.editingQuestionId = q.id;
    this.questionForm.patchValue({
      category: q.category,
      question_text: q.question_text,
      keywords: q.keywords,
      ideal_answer: q.ideal_answer || ''
    });
    this.formErrorMessage = null;
    this.formSuccessMessage = null;
    
    // Scroll to form
    const formElement = document.getElementById('question-form-section');
    if (formElement) {
      formElement.scrollIntoView({ behavior: 'smooth' });
    }
  }

  onDeleteQuestion(id: number) {
    if (confirm("Are you sure you want to delete this question? Candidates will no longer be asked this during new sessions.")) {
      this.adminService.deleteQuestion(id).subscribe({
        next: () => {
          this.loadQuestions();
        },
        error: (err) => {
          alert(err.error?.message || "Failed to delete question.");
        }
      });
    }
  }

  resetForm() {
    this.isEditing = false;
    this.editingQuestionId = null;
    this.questionForm.reset({
      category: 'HR',
      question_text: '',
      keywords: '',
      ideal_answer: ''
    });
  }
}
