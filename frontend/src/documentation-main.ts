import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter, withInMemoryScrolling } from '@angular/router';
import { AppShell } from './app/app-shell';
import { Documentation } from './app/documentation/documentation';

bootstrapApplication(AppShell, {
  providers: [provideRouter([
    { path: '', component: Documentation, pathMatch: 'full' },
    { path: 'documentation', component: Documentation },
    { path: 'documentation/:page', component: Documentation },
    { path: '**', redirectTo: 'documentation' },
  ], withInMemoryScrolling({ scrollPositionRestoration: 'enabled', anchorScrolling: 'enabled' }))],
}).catch(error => console.error(error));
