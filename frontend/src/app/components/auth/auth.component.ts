import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterLink],
  templateUrl: './auth.component.html',
  styleUrls: ['./auth.component.css']
})
export class AuthComponent {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);

  isLoginMode = true;
  forgotMode: 'request' | 'reset' | 'none' = 'none';
  errorMessage: string | null = null;
  successMessage: string | null = null;
  mockedCodeNotice: string | null = null;
  loading = false;

  // Recovery Form Fields
  forgotEmail = '';
  resetCode = '';
  newPassword = '';
  confirmPassword = '';

  authForm: FormGroup = this.fb.group({
    name: [''], // Will dynamically require this on mode toggle
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]]
  });

  toggleMode() {
    this.isLoginMode = !this.isLoginMode;
    this.errorMessage = null;
    this.successMessage = null;
    this.mockedCodeNotice = null;
    
    const nameControl = this.authForm.get('name');
    if (this.isLoginMode) {
      nameControl?.clearValidators();
    } else {
      nameControl?.setValidators([Validators.required, Validators.minLength(2)]);
    }
    nameControl?.updateValueAndValidity();
  }

  startForgotPassword(event: Event) {
    event.preventDefault();
    this.forgotMode = 'request';
    this.errorMessage = null;
    this.successMessage = null;
    this.mockedCodeNotice = null;
    this.forgotEmail = this.authForm.get('email')?.value || '';
  }

  cancelForgotPassword() {
    this.forgotMode = 'none';
    this.errorMessage = null;
    this.successMessage = null;
    this.mockedCodeNotice = null;
    this.authForm.patchValue({ email: this.forgotEmail });
  }

  requestResetCode() {
    if (!this.forgotEmail || !this.forgotEmail.includes('@')) {
      this.errorMessage = "Please enter a valid email address.";
      return;
    }

    this.loading = true;
    this.errorMessage = null;
    this.successMessage = null;
    this.mockedCodeNotice = null;

    this.authService.forgotPassword(this.forgotEmail).subscribe({
      next: (res) => {
        this.loading = false;
        this.forgotMode = 'reset';
        this.successMessage = "A reset verification code has been simulated for your email address.";
        this.mockedCodeNotice = `[Mock Dev Mode] Your 6-digit reset code is: ${res.code}`;
        this.resetCode = '';
        this.newPassword = '';
        this.confirmPassword = '';
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err.error?.message || "No registered account was found with this email.";
      }
    });
  }

  submitResetPassword() {
    if (!this.resetCode || this.resetCode.length !== 6) {
      this.errorMessage = "Please enter a valid 6-digit code.";
      return;
    }
    if (!this.newPassword || this.newPassword.length < 6) {
      this.errorMessage = "Password must be at least 6 characters.";
      return;
    }
    if (this.newPassword !== this.confirmPassword) {
      this.errorMessage = "Passwords do not match.";
      return;
    }

    this.loading = true;
    this.errorMessage = null;
    this.successMessage = null;
    this.mockedCodeNotice = null;

    this.authService.resetPassword(this.forgotEmail, this.resetCode, this.newPassword).subscribe({
      next: (res) => {
        this.loading = false;
        this.forgotMode = 'none';
        this.isLoginMode = true;
        this.successMessage = "Your password has been successfully reset. Please log in.";
        this.authForm.patchValue({ email: this.forgotEmail, password: '' });
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err.error?.message || "Invalid or expired reset code.";
      }
    });
  }

  onSubmit() {
    if (this.authForm.invalid) {
      this.errorMessage = "Please enter valid credentials.";
      return;
    }

    this.loading = true;
    this.errorMessage = null;
    this.successMessage = null;
    this.mockedCodeNotice = null;
    const { name, email, password } = this.authForm.value;

    if (this.isLoginMode) {
      this.authService.login(email, password).subscribe({
        next: (res) => {
          this.loading = false;
          if (res.user.role === 'admin') {
            this.router.navigate(['/admin']);
          } else {
            this.router.navigate(['/dashboard']);
          }
        },
        error: (err) => {
          this.loading = false;
          this.errorMessage = err.error?.message || "Login failed. Please check credentials.";
        }
      });
    } else {
      this.authService.register(name, email, password).subscribe({
        next: () => {
          this.loading = false;
          this.router.navigate(['/dashboard']);
        },
        error: (err) => {
          this.loading = false;
          this.errorMessage = err.error?.message || "Signup failed. Email might already be in use.";
        }
      });
    }
  }
}
