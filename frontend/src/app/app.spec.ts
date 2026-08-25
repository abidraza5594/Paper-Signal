import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { App, MAX_FILE_BYTES, buildSchemaFromFields, validateJsonSchema, validatePdfFile } from './app';
import { API_KEY_STORAGE, apiKeyInterceptor, readStoredApiKey, storeApiKey } from './api-key';

const VALID_SCHEMA = JSON.stringify({
  type: 'object',
  properties: { total: { type: 'string' } },
});

describe('PDF file validation', () => {
  it('accepts a PDF at the 200 MB limit', () => {
    const file = new File([new Uint8Array(10)], 'report.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: MAX_FILE_BYTES });
    expect(validatePdfFile(file)).toBeNull();
  });

  it('rejects files larger than 200 MB', () => {
    const file = new File(['data'], 'large.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: MAX_FILE_BYTES + 1 });
    expect(validatePdfFile(file)).toContain('larger than 200 MB');
  });

  it('rejects non-PDF files', () => {
    expect(validatePdfFile(new File(['data'], 'notes.txt', { type: 'text/plain' }))).toBe('Please choose a PDF file.');
  });
});

describe('JSON Schema validation', () => {
  it('accepts a nested object schema', () => {
    expect(validateJsonSchema(JSON.stringify({
      type: 'object',
      properties: {
        education: {
          type: 'object',
          properties: { degree: { type: 'string' } },
        },
      },
    }))).toBeNull();
  });

  it('rejects free text and example objects immediately', () => {
    expect(validateJsonSchema('lorem')).toContain('Invalid JSON');
    expect(validateJsonSchema('{"name":"string"}')).toContain('Root type');
  });
});

describe('Simple field builder', () => {
  it('turns named fields into a valid JSON Schema', () => {
    const schema = buildSchemaFromFields([
      { name: 'trainName', type: 'text' },
      { name: 'trainNumber', type: 'number' },
      { name: 'isCancelled', type: 'boolean' },
      { name: 'stops', type: 'list' },
    ]);

    expect(validateJsonSchema(schema)).toBeNull();
    expect(JSON.parse(schema)).toEqual({
      type: 'object',
      properties: {
        trainName: { type: 'string' },
        trainNumber: { type: 'number' },
        isCancelled: { type: 'boolean' },
        stops: { type: 'array', items: { type: 'string' } },
      },
    });
  });

  it('ignores blank rows and produces nothing when no field is named', () => {
    expect(buildSchemaFromFields([{ name: '  ', type: 'text' }])).toBe('');
    expect(JSON.parse(buildSchemaFromFields([{ name: '', type: 'text' }, { name: 'total', type: 'number' }]))).toEqual({
      type: 'object',
      properties: { total: { type: 'number' } },
    });
  });
});

describe('API key handling', () => {
  afterEach(() => localStorage.removeItem(API_KEY_STORAGE));

  it('stores and clears the key in local storage', () => {
    storeApiKey('  ps_live_abc123  ');
    expect(readStoredApiKey()).toBe('ps_live_abc123');
    storeApiKey('');
    expect(readStoredApiKey()).toBe('');
  });

  it('attaches the key only to api requests', () => {
    storeApiKey('ps_live_abc123');
    const seen: (string | null)[] = [];
    const next = (req: any) => {
      seen.push(req.headers.get('X-API-Key'));
      return req;
    };

    apiKeyInterceptor({ url: '/api/jobs', headers: { get: () => null }, clone: (o: any) => ({ headers: { get: () => o.setHeaders['X-API-Key'] } }) } as any, next as any);
    apiKeyInterceptor({ url: 'https://elsewhere.test/data', headers: { get: () => null }, clone: () => ({}) } as any, next as any);

    expect(seen[0]).toBe('ps_live_abc123');
    expect(seen[1]).toBeNull();
  });

  it('sends no header when no key is stored', () => {
    storeApiKey('');
    let cloned = false;
    apiKeyInterceptor({ url: '/api/jobs', clone: () => ((cloned = true), {}) } as any, ((r: any) => r) as any);
    expect(cloned).toBe(false);
  });
});

describe('App states', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('shows the empty result workspace when connected', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    http.expectOne('/api/jobs?limit=20').flush([]);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No results yet');
  });

  it('disables extraction and explains configuration when AI is unavailable', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: false, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    http.expectOne('/api/jobs?limit=20').flush([]);
    fixture.detectChanges();
    const button = fixture.nativeElement.querySelector('.primary-action') as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('MISTRAL_API_KEY');
  });

  it('enables extraction only when a valid JSON Schema is entered after selecting a PDF', () => {
    const fixture = TestBed.createComponent(App);
    const component = fixture.componentInstance;
    component.health.set({
      status: 'ok',
      ai_configured: true,
      max_upload_mb: 200,
      max_pdf_pages: 40,
      text_model: 'mistral-small',
      vision_model: 'mistral-small',
      ocr_model: 'mistral-ocr',
    });
    component.selectFile(new File(['%PDF-1.7'], 'report.pdf', { type: 'application/pdf' }));

    expect(component.canSubmit()).toBe(false);
    component.outputTemplate = 'lorem';
    component.validateSchemaInput();
    expect(component.canSubmit()).toBe(false);
    expect(component.schemaError).toContain('Invalid JSON');
    component.outputTemplate = VALID_SCHEMA;
    component.validateSchemaInput();

    expect(component.canSubmit()).toBe(true);
  });

  it('keeps valid PDFs when a duplicate is added and records the duplicate reason', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.addFiles([
      new File(['%PDF-1.7'], 'invoice.pdf', { type: 'application/pdf' }),
      new File(['%PDF-1.7'], 'invoice.pdf', { type: 'application/pdf' }),
    ]);

    expect(app.selectedFiles().length).toBe(1);
    expect(app.fileRejections()[0].error).toContain('already in the batch');
  });

  it('enforces the combined batch limit without discarding earlier files', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, max_batch_files: 5, max_batch_total_mb: 1, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    const first = new File(['one'], 'one.pdf', { type: 'application/pdf' });
    const second = new File(['two'], 'two.pdf', { type: 'application/pdf' });
    Object.defineProperty(first, 'size', { value: 700 * 1024 });
    Object.defineProperty(second, 'size', { value: 700 * 1024 });
    app.addFiles([first, second]);

    expect(app.selectedFiles()).toEqual([first]);
    expect(app.fileRejections()[0].error).toContain('Batch total');
  });

  it('submits all valid files to the batch endpoint and tracks returned jobs', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    app.addFiles([new File(['a'], 'one.pdf', { type: 'application/pdf' }), new File(['b'], 'two.pdf', { type: 'application/pdf' })]);
    app.outputTemplate = VALID_SCHEMA;
    app.validateSchemaInput();
    app.submit();

    const request = http.expectOne('/api/jobs/batch');
    expect(request.request.method).toBe('POST');
    expect((request.request.body as FormData).getAll('files').length).toBe(2);
    request.flush({ jobs: [{ id: 'batch-job', status: 'queued', progress: 0, file_name: 'one.pdf' }], rejected: [{ file_name: 'two.pdf', error: 'Page count exceeded' }], accepted_count: 1, rejected_count: 1 });

    expect(app.batchSummary()?.accepted_count).toBe(1);
    expect(app.activeJob()?.id).toBe('batch-job');
    expect(app.recentJobs()[0].id).toBe('batch-job');
    http.expectOne('/api/jobs/batch-job').flush({ id: 'batch-job', status: 'completed', progress: 100, file_name: 'one.pdf', result: {} });
    http.expectOne('/api/jobs?limit=20').flush([]);
  });

  it('opens on the JSON Schema editor and shows the service limits', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance.inputMode()).toBe('advanced');
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    http.expectOne('/api/jobs?limit=20').flush([]);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('max 40 pages');
    expect(fixture.nativeElement.textContent).toContain('Only JSON Schema is accepted');
    expect(fixture.nativeElement.textContent).toContain('Missing values become');
    expect(fixture.nativeElement.textContent).toContain('extra fields are removed');
    expect(fixture.nativeElement.querySelector('#template')).toBeTruthy();
    expect(fixture.nativeElement.querySelectorAll('.schema-checks span').length).toBe(4);
  });

  it('marks each schema check as the pasted JSON Schema becomes valid', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    http.expectOne('/api/jobs?limit=20').flush([]);

    app.outputTemplate = '{trainName:"string"}';
    app.validateSchemaInput();
    expect(app.schemaChecks()).toEqual({ validJson: false, rootObject: false, properties: false, supported: false });
    expect(app.schemaError).toContain('Invalid JSON');

    app.outputTemplate = VALID_SCHEMA;
    app.validateSchemaInput();
    expect(app.schemaChecks()).toEqual({ validJson: true, rootObject: true, properties: true, supported: true });
    expect(app.schemaError).toBe('');
  });

  it('renders the extraction audit and calculates OCR coverage', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    app.activeJob.set({ id: 'job-123', status: 'completed', progress: 100, file_name: 'report.pdf', file_size: 2048, page_count: 40, python_text_pages: 31, vision_attempted_pages: 9, vision_pages: 6, vision_failed_pages: 3, ocr_pages: 3, ocr_mode: 'auto', text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr', schema_mode: 'json_schema', result: { data: {} } });
    app.expandedJobId.set('job-123');
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    http.expectOne('/api/jobs?limit=20').flush([]);
    expect(app.ocrCoverage(app.activeJob()!)).toBe(8);
    expect(fixture.nativeElement.textContent).toContain('Extraction audit');
    expect(fixture.nativeElement.querySelector('.json-view')).toBeTruthy();
    expect(fixture.nativeElement.textContent).toContain('31');
    expect(fixture.nativeElement.textContent).toContain('9');
    expect(fixture.nativeElement.textContent).toContain('Vision model');
    expect(fixture.nativeElement.textContent).toContain('6');
  });

  it('falls back cleanly for older jobs without vision fields', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    const oldJob = { id: 'old-job', status: 'completed' as const, progress: 100, page_count: 4, ocr_pages: 0, result: { data: {} } };
    app.activeJob.set(oldJob);
    app.expandedJobId.set('old-job');
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    http.expectOne('/api/jobs?limit=20').flush([]);
    expect(app.visionPages(oldJob)).toBe(0);
    expect(app.visionModel(oldJob)).toBe('Not used');
    expect(app.routeSummary(oldJob)).toBe('P 4 / V 0 / O 0');
    expect(fixture.nativeElement.textContent).toContain('Not used');
  });

  it('marks only Python as used when Vision and OCR were not needed', () => {
    const fixture = TestBed.createComponent(App);
    fixture.componentInstance.activeJob.set({
      id: 'python-only',
      status: 'processing',
      progress: 32,
      stage: 'Preparing 1 extraction section(s)',
      page_count: 1,
      python_text_pages: 1,
      vision_attempted_pages: 0,
      ocr_pages: 0,
    });
    fixture.componentInstance.expandedJobId.set('python-only');
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    http.expectOne('/api/jobs?limit=20').flush([]);

    expect(fixture.nativeElement.querySelector('.python-step').classList).toContain('done');
    expect(fixture.nativeElement.querySelector('.vision-step').classList).toContain('skipped');
    expect(fixture.nativeElement.querySelector('.vision-step').classList).not.toContain('done');
    expect(fixture.nativeElement.querySelector('.ocr-step').classList).toContain('skipped');
    expect(fixture.nativeElement.querySelector('.ocr-step').classList).not.toContain('done');
  });

  it('marks Vision and OCR only when those fallbacks were reached', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    const visionJob = {
      id: 'vision-only',
      status: 'processing' as const,
      progress: 32,
      stage: 'Preparing 1 extraction section(s)',
      page_count: 1,
      python_text_pages: 0,
      vision_attempted_pages: 1,
      vision_pages: 1,
      ocr_pages: 0,
    };

    expect(app.readingRouteIsDone(visionJob, 'vision')).toBe(true);
    expect(app.readingRouteWasSkipped(visionJob, 'ocr')).toBe(true);
    expect(app.readingRouteIsDone({ ...visionJob, vision_pages: 0, ocr_pages: 1 }, 'ocr')).toBe(true);
  });

  it('keeps every batch file on the board and shows each result separately', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    app.addFiles([new File(['a'], 'kalyan.pdf', { type: 'application/pdf' }), new File(['b'], 'bangalore.pdf', { type: 'application/pdf' })]);
    app.outputTemplate = VALID_SCHEMA;
    app.validateSchemaInput();
    app.submit();

    http.expectOne('/api/jobs/batch').flush({
      jobs: [
        { id: 'job-a', status: 'queued', progress: 0, file_name: 'kalyan.pdf' },
        { id: 'job-b', status: 'queued', progress: 0, file_name: 'bangalore.pdf' },
      ],
      rejected: [],
      accepted_count: 2,
      rejected_count: 0,
    });

    expect(app.batchJobs().length).toBe(2);
    expect(app.activeJob()?.id).toBe('job-a');

    http.expectOne('/api/jobs/job-a').flush({ id: 'job-a', status: 'completed', progress: 100, file_name: 'kalyan.pdf', result: { data: { trainName: 'UDAYAN EXP', trainNumber: 11302 } } });
    http.expectOne('/api/jobs?limit=20').flush([]);
    http.expectOne('/api/jobs/job-b').flush({ id: 'job-b', status: 'completed', progress: 100, file_name: 'bangalore.pdf', result: { data: { trainName: 'UDAYAN EXP', trainNumber: 11301 } } });
    http.expectOne('/api/jobs?limit=20').flush([]);

    expect(app.batchFinishedCount()).toBe(2);
    expect(app.batchCombined().map((item) => item.file)).toEqual(['kalyan.pdf', 'bangalore.pdf']);
    expect(app.resultFields(app.batchJobs()[0])).toEqual([
      { key: 'trainName', value: 'UDAYAN EXP' },
      { key: 'trainNumber', value: '11302' },
    ]);
    expect(app.resultFields(app.batchJobs()[1])[1].value).toBe('11301');
  });

  it('does not switch the open audit when another batch job finishes', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    app.addFiles([new File(['a'], 'one.pdf', { type: 'application/pdf' }), new File(['b'], 'two.pdf', { type: 'application/pdf' })]);
    app.outputTemplate = VALID_SCHEMA;
    app.validateSchemaInput();
    app.submit();

    http.expectOne('/api/jobs/batch').flush({
      jobs: [
        { id: 'job-a', status: 'queued', progress: 0, file_name: 'one.pdf' },
        { id: 'job-b', status: 'queued', progress: 0, file_name: 'two.pdf' },
      ],
      rejected: [],
      accepted_count: 2,
      rejected_count: 0,
    });

    http.expectOne('/api/jobs/job-a').flush({ id: 'job-a', status: 'processing', progress: 40, file_name: 'one.pdf' });
    http.expectOne('/api/jobs/job-b').flush({ id: 'job-b', status: 'completed', progress: 100, file_name: 'two.pdf', result: { data: { trainNumber: 11301 } } });
    http.expectOne('/api/jobs?limit=20').flush([]);

    expect(app.activeJob()?.id).toBe('job-a');
    expect(app.batchJobs()[1].status).toBe('completed');
  });

  it('lists each batch file by name and shows its JSON only when opened', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.batchJobs.set([
      { id: 'job-a', status: 'completed', progress: 100, file_name: 'kalyan.pdf', result: { data: { trainName: 'UDAYAN EXPRESS', trainNumber: 11302 } } },
      { id: 'job-b', status: 'completed', progress: 100, file_name: 'bangalore.pdf', result: { data: { trainName: 'UDAYAN EXPRESS', trainNumber: 11301 } } },
    ]);
    fixture.detectChanges();
    http.expectOne('/api/health');
    http.expectOne('/api/jobs?limit=20');

    // collapsed by default: only the file names are listed, no values on screen
    const items = fixture.nativeElement.querySelectorAll('.result-item');
    expect(items.length).toBe(2);
    expect(items[0].textContent).toContain('kalyan.pdf');
    expect(items[1].textContent).toContain('bangalore.pdf');
    expect(fixture.nativeElement.querySelector('.json-view')).toBeNull();

    // opening one reveals that file's JSON only
    app.toggleDetails(app.tableJobs()[0]);
    fixture.detectChanges();
    const open = fixture.nativeElement.querySelectorAll('.json-view');
    expect(open.length).toBe(1);
    expect(JSON.parse(open[0].textContent)).toEqual({ trainName: 'UDAYAN EXPRESS', trainNumber: 11302 });
  });

  it('restores the whole batch board when a batch job is reopened after a reload', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;

    app.openJob({ id: 'job-b', status: 'completed', progress: 100 });
    http.expectOne('/api/jobs/job-b').flush({ id: 'job-b', batch_id: 'batch-1', status: 'completed', progress: 100, file_name: 'bangalore.pdf', result: { data: { trainNumber: 11301 } } });
    http.expectOne('/api/batches/batch-1').flush([
      { id: 'job-a', batch_id: 'batch-1', status: 'completed', progress: 100, file_name: 'kalyan.pdf', result: { data: { trainNumber: 11302 } } },
      { id: 'job-b', batch_id: 'batch-1', status: 'completed', progress: 100, file_name: 'bangalore.pdf', result: { data: { trainNumber: 11301 } } },
    ]);

    expect(app.batchJobs().length).toBe(2);
    expect(app.activeJob()?.id).toBe('job-b');
    expect(app.batchCombined().map((item) => item.file)).toEqual(['kalyan.pdf', 'bangalore.pdf']);
  });

  it('shows only the single job when it was not part of a batch', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.batchJobs.set([{ id: 'old-a', status: 'completed', progress: 100 }, { id: 'old-b', status: 'completed', progress: 100 }]);

    app.openJob({ id: 'solo', status: 'completed', progress: 100 });
    http.expectOne('/api/jobs/solo').flush({ id: 'solo', status: 'completed', progress: 100, file_name: 'solo.pdf', result: {} });

    expect(app.batchJobs()).toEqual([]);
  });

  it('queues a second batch under the running one without restarting it', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    app.addFiles([new File(['a'], 'one.pdf', { type: 'application/pdf' }), new File(['b'], 'two.pdf', { type: 'application/pdf' })]);
    app.outputTemplate = VALID_SCHEMA;
    app.validateSchemaInput();
    app.submit();

    http.expectOne('/api/jobs/batch').flush({
      batch_id: 'batch-1',
      jobs: [
        { id: 'job-a', batch_id: 'batch-1', status: 'queued', progress: 0, file_name: 'one.pdf' },
        { id: 'job-b', batch_id: 'batch-1', status: 'queued', progress: 0, file_name: 'two.pdf' },
      ],
      rejected: [],
      accepted_count: 2,
      rejected_count: 0,
    });
    http.expectOne('/api/jobs/job-a').flush({ id: 'job-a', batch_id: 'batch-1', status: 'processing', progress: 45, file_name: 'one.pdf' });
    http.expectOne('/api/jobs/job-b').flush({ id: 'job-b', batch_id: 'batch-1', status: 'processing', progress: 30, file_name: 'two.pdf' });

    // the composer is empty again, so already-submitted PDFs cannot be re-uploaded
    expect(app.selectedFiles()).toEqual([]);

    app.addFiles([new File(['c'], 'three.pdf', { type: 'application/pdf' })]);
    app.submit();
    const second = http.expectOne('/api/jobs/batch');
    expect((second.request.body as FormData).getAll('files').length).toBe(1);
    second.flush({
      batch_id: 'batch-2',
      jobs: [{ id: 'job-c', batch_id: 'batch-2', status: 'queued', progress: 0, file_name: 'three.pdf' }],
      rejected: [],
      accepted_count: 1,
      rejected_count: 0,
    });

    // the running batch stays on the board, the new file is appended below it
    expect(app.batchJobs().map((job) => job.id)).toEqual(['job-a', 'job-b', 'job-c']);
    expect(app.batchJobs()[0].progress).toBe(45);
    expect(app.batchJobs()[1].progress).toBe(30);
    expect(app.batchJobs()[2].status).toBe('queued');

    // and the panel keeps showing the job that is still running
    expect(app.activeJob()?.id).toBe('job-a');

    // every earlier job is still polled, so its progress keeps moving
    http.expectOne('/api/jobs/job-c').flush({ id: 'job-c', batch_id: 'batch-2', status: 'queued', progress: 0, file_name: 'three.pdf' });
    fixture.destroy();
  });

  it('lets a user opt into simple fields instead of writing JSON Schema', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'mistral-small', vision_model: 'mistral-small', ocr_model: 'mistral-ocr' });
    app.useSimpleFields();
    app.addFiles([new File(['a'], 'train.pdf', { type: 'application/pdf' })]);

    expect(app.canSubmit()).toBe(false);

    app.updateFieldName(0, 'trainName');
    app.addField();
    app.updateFieldName(1, 'trainNumber');
    app.updateFieldType(1, 'number');

    expect(app.schemaError).toBe('');
    expect(app.canSubmit()).toBe(true);
    expect(app.columns()).toEqual(['trainName', 'trainNumber']);

    app.submit();
    const request = http.expectOne('/api/jobs/batch');
    expect(JSON.parse((request.request.body as FormData).get('output_template') as string)).toEqual({
      type: 'object',
      properties: { trainName: { type: 'string' }, trainNumber: { type: 'number' } },
    });
    request.flush({ batch_id: 'b1', jobs: [{ id: 'j1', batch_id: 'b1', status: 'queued', progress: 0, file_name: 'train.pdf' }], rejected: [], accepted_count: 1, rejected_count: 0 });

    // the setup panel folds away so the results own the screen
    expect(app.setupOpen()).toBe(false);

    http.expectOne('/api/jobs/j1').flush({ id: 'j1', batch_id: 'b1', status: 'completed', progress: 100, file_name: 'train.pdf', result: { data: { trainName: 'UDYAN EXPRESS', trainNumber: 11301 } } });
    http.expectOne('/api/jobs?limit=20').flush([]);

    expect(app.cellValue(app.tableJobs()[0], 'trainNumber')).toBe('11301');
    expect(app.statusLabel(app.tableJobs()[0])).toBe('Done');
  });

  it('shows empty columns for values a PDF did not contain', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    const job = { id: 'j2', status: 'completed' as const, progress: 100, file_name: 'partial.pdf', result: { data: { trainName: 'UDYAN', trainNumber: null } } };
    app.batchJobs.set([job]);

    expect(app.columns()).toEqual(['trainName', 'trainNumber']);
    expect(app.cellValue(job, 'trainName')).toBe('UDYAN');
    expect(app.cellValue(job, 'trainNumber')).toBe('—');
    expect(app.cellValue({ id: 'j3', status: 'processing', progress: 20 }, 'trainName')).toBe('');
  });

  it('asks for a key when the service runs in key mode', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    localStorage.removeItem(API_KEY_STORAGE);
    app.apiKey.set('');
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, require_api_key: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'm', vision_model: 'm', ocr_model: 'm' });
    http.expectOne('/api/jobs?limit=20').flush([]);
    fixture.detectChanges();

    expect(app.needsApiKey()).toBe(true);
    expect(fixture.nativeElement.querySelector('.key-gate')).toBeTruthy();

    app.apiKeyDraft.set('ps_live_test123456');
    app.saveApiKey();
    expect(app.apiKey()).toBe('ps_live_test123456');
    expect(app.maskedApiKey()).toBe('ps_live_test12…');
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, require_api_key: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'm', vision_model: 'm', ocr_model: 'm' });
    http.expectOne('/api/jobs?limit=20').flush([]);
    fixture.detectChanges();

    expect(app.needsApiKey()).toBe(false);
    expect(fixture.nativeElement.querySelector('.key-gate')).toBeNull();
    app.clearApiKey();
    localStorage.removeItem(API_KEY_STORAGE);
  });

  it('re-opens the key gate when the server rejects the stored key', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.health.set({ status: 'ok', ai_configured: true, require_api_key: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'm', vision_model: 'm', ocr_model: 'm' });
    app.apiKey.set('ps_live_stale');
    expect(app.needsApiKey()).toBe(false);

    app.loadRecentJobs();
    http.expectOne('/api/jobs?limit=20').flush({ detail: 'revoked' }, { status: 401, statusText: 'Unauthorized' });

    expect(app.needsApiKey()).toBe(true);
    app.clearApiKey();
  });

  it('brings the last batch back after a page reload', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'm', vision_model: 'm', ocr_model: 'm' });

    // a fresh page load only knows what the registry returns
    http.expectOne('/api/jobs?limit=20').flush([
      { id: 'job-b', batch_id: 'batch-1', status: 'completed', progress: 100, file_name: 'b.pdf', output_template: VALID_SCHEMA, result: { data: { total: '20' } } },
      { id: 'job-a', batch_id: 'batch-1', status: 'completed', progress: 100, file_name: 'a.pdf', result: { data: { total: '10' } } },
    ]);
    http.expectOne('/api/batches/batch-1').flush([
      { id: 'job-a', batch_id: 'batch-1', status: 'completed', progress: 100, file_name: 'a.pdf', result: { data: { total: '10' } } },
      { id: 'job-b', batch_id: 'batch-1', status: 'completed', progress: 100, file_name: 'b.pdf', result: { data: { total: '20' } } },
    ]);
    fixture.detectChanges();

    // both files are listed again, and the schema that produced them is back in the editor
    expect(app.tableJobs().map((job) => job.id)).toEqual(['job-a', 'job-b']);
    expect(app.setupOpen()).toBe(false);
    expect(app.outputTemplate).toBe(VALID_SCHEMA);
    expect(fixture.nativeElement.querySelectorAll('.result-item').length).toBe(2);
    // rows stay collapsed until the user opens one
    expect(fixture.nativeElement.querySelector('.json-view')).toBeNull();
  });

  it('leaves the empty state alone when there is no history to restore', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok', ai_configured: true, max_upload_mb: 200, max_pdf_pages: 40, text_model: 'm', vision_model: 'm', ocr_model: 'm' });
    http.expectOne('/api/jobs?limit=20').flush([]);
    fixture.detectChanges();

    expect(app.tableJobs()).toEqual([]);
    expect(app.setupOpen()).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('No results yet');
  });

  it('renders a specific rejection near the submit action', () => {
    const fixture = TestBed.createComponent(App);
    fixture.componentInstance.submitError = 'PDF rejected: 41 pages detected. Maximum allowed is 40 pages.';
    fixture.detectChanges();
    http.expectOne('/api/health');
    http.expectOne('/api/jobs?limit=20');
    expect(fixture.nativeElement.querySelector('.submit-error').textContent).toContain('Maximum allowed is 40 pages');
  });
});
