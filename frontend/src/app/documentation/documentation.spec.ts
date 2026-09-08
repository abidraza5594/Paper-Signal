import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { Documentation } from './documentation';

describe('Developer documentation navigation', () => {
  beforeEach(() => TestBed.configureTestingModule({
    providers: [provideRouter([
      { path: 'documentation', component: Documentation },
      { path: 'documentation/:page', component: Documentation },
    ])],
  }));

  it('opens the public overview without a credential or API request', async () => {
    const harness = await RouterTestingHarness.create('/documentation');
    expect(harness.routeNativeElement?.querySelector('h1')?.textContent).toBe('Build with PaperSignal');
    expect(harness.routeNativeElement?.querySelector('.base-url')?.textContent).toContain('https://papersignal.duckdns.org');
  });

  it('supports direct endpoint links and keeps the correct auth context on navigation', async () => {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/documentation/upload', Documentation);
    expect(harness.routeNativeElement?.querySelector('.endpoint-bar')?.textContent).toContain('/api/jobs');
    await harness.navigateByUrl('/documentation/create-key', Documentation);
    expect(harness.routeNativeElement?.querySelector('.auth-line')?.textContent).toContain('X-Admin-Token');
    expect(harness.routeNativeElement?.querySelector('.endpoint-bar')?.textContent).toContain('201 Created');
  });

  it('filters reference topics by path and offers a useful empty state', async () => {
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/documentation', Documentation);
    component.query.set('/api/admin/keys');
    harness.detectChanges();
    expect(component.groups().flatMap(group => group.pages).some(page => page.id === 'create-key')).toBe(true);
    component.query.set('zz-no-such-topic-zz');
    harness.detectChanges();
    expect(harness.routeNativeElement?.querySelector('.search-empty')?.textContent).toContain('No matching topics');
  });

  it('switches copyable examples to Node.js using native multipart Blob', async () => {
    const harness = await RouterTestingHarness.create();
    const component = await harness.navigateByUrl('/documentation/quickstart', Documentation);
    component.language.set('Node.js');
    harness.detectChanges();
    expect(harness.routeNativeElement?.querySelector('.sample-section pre')?.textContent).toContain('new Blob');
    expect(harness.routeNativeElement?.querySelector('.sample-section pre')?.textContent).toContain('PAPERSIGNAL_API_KEY');
  });
});
