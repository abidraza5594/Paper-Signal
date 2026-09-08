import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withInMemoryScrolling } from '@angular/router';
import { App } from './app';

import { apiKeyInterceptor } from './api-key';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter([
      { path: 'documentation', loadComponent: () => import('./documentation/documentation').then(m => m.Documentation) },
      { path: 'documentation/:page', loadComponent: () => import('./documentation/documentation').then(m => m.Documentation) },
      { path: '', component: App, pathMatch: 'full' },
      { path: '**', redirectTo: '' },
    ], withInMemoryScrolling({ scrollPositionRestoration: 'enabled', anchorScrolling: 'enabled' })),
    provideHttpClient(withInterceptors([apiKeyInterceptor])),
  ],
};
