import { Routes } from '@angular/router';
import { LandingComponent } from './components/landing/landing.component';
import { AuthComponent } from './components/auth/auth.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { InterviewRoomComponent } from './components/interview-room/interview-room.component';
import { ResultAnalysisComponent } from './components/result-analysis/result-analysis.component';
import { AdminComponent } from './components/admin/admin.component';
import { authGuard, loginGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', component: LandingComponent },
  { path: 'login', component: AuthComponent, canActivate: [loginGuard] },
  { path: 'dashboard', component: DashboardComponent, canActivate: [authGuard] },
  { path: 'interview-room/:category', component: InterviewRoomComponent, canActivate: [authGuard] },
  { path: 'result/:id', component: ResultAnalysisComponent, canActivate: [authGuard] },
  { path: 'admin', component: AdminComponent, canActivate: [authGuard], data: { role: 'admin' } },
  { path: '**', redirectTo: '' }
];
