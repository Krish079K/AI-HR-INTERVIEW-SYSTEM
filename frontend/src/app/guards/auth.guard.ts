import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isLoggedIn()) {
    // Check if role-based restriction exists (e.g., admin check)
    if (route.data && route.data['role'] === 'admin') {
      if (authService.isAdmin()) {
        return true;
      } else {
        router.navigate(['/dashboard']);
        return false;
      }
    }
    return true;
  }

  // Redirect to login if unauthenticated
  router.navigate(['/login']);
  return false;
};
export const loginGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isLoggedIn()) {
    router.navigate(['/dashboard']);
    return false;
  }
  return true;
};
