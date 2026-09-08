import { CommonModule } from '@angular/common';
import { HttpClient, HttpEventType, HttpRequest } from '@angular/common/http';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { readStoredApiKey, storeApiKey } from './api-key';

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type OcrMode = 'auto' | 'always' | 'never';
export type ResultTab = 'data' | 'evidence' | 'raw';
export type ReadingRoute = 'python' | 'vision' | 'ocr';

export interface HealthResponse {
  status: string;
  ai_configured: boolean;
  max_upload_mb: number;
  max_pdf_pages: number;
  text_model: string;
  vision_model: string;
  ocr_model: string;
  max_batch_files?: number;
  max_batch_total_mb?: number;
  require_api_key?: boolean;
}

export interface BatchRejection {
  file_name: string;
  error: string;
}

export interface BatchResponse {
  extraction_id?: string;
  jobs: PdfJob[];
  rejected: BatchRejection[];
  accepted_count: number;
  rejected_count: number;
}

export interface EvidenceItem {
  page?: number;
  page_number?: number;
  label?: string;
  evidence?: string;
  field?: string;
  quote?: string;
  text?: string;
  [key: string]: unknown;
}

export interface JobResult {
  data?: unknown;
  structured_data?: unknown;
  evidence?: EvidenceItem[];
  [key: string]: unknown;
}

export interface PdfJob {
  id: string;
  extraction_id?: string | null;
  status: JobStatus;
  progress: number;
  stage?: string;
  error?: string | null;
  result?: JobResult | unknown;
  filename?: string;
  file_name?: string;
  created_at?: string;
  updated_at?: string;
  instruction?: string;
  file_size?: number;
  page_count?: number | null;
  ocr_pages?: number;
  python_text_pages?: number;
  text_model?: string | null;
  vision_model?: string | null;
  vision_attempted_pages?: number;
  vision_pages?: number;
  vision_failed_pages?: number;
  ocr_model?: string | null;
  schema_mode?: 'json_schema' | 'example' | 'none' | string;
  output_template?: string | null;
  duration_ms?: number | null;
  failure_code?: string | null;
  failure_stage?: string | null;
  ocr_mode?: OcrMode;
}

export const MAX_FILE_BYTES = 200 * 1024 * 1024;
export const DEFAULT_MAX_BATCH_FILES = 10;
export const DEFAULT_MAX_BATCH_BYTES = 500 * 1024 * 1024;

export function validatePdfFile(file: File, maxFileBytes = MAX_FILE_BYTES): string | null {
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  if (!isPdf) return 'Please choose a PDF file.';
  if (file.size > maxFileBytes) return `This PDF is larger than ${Math.round(maxFileBytes / 1024 / 1024)} MB. Please choose a smaller file.`;
  if (file.size === 0) return 'This PDF is empty. Please choose another file.';
  return null;
}

const SUPPORTED_SCHEMA_TYPES = new Set([
  'object',
  'array',
  'string',
  'number',
  'integer',
  'boolean',
  'null',
]);

function validateSchemaNode(value: unknown, path: string, depth: number): string | null {
  if (depth > 8) return 'JSON Schema nesting cannot exceed 8 levels.';
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return `${path} must be a JSON Schema object.`;
  }

  const node = value as Record<string, unknown>;
  const unsupportedComposition = ['$ref', 'allOf', 'anyOf', 'oneOf', 'not'].find(
    (key) => key in node,
  );
  if (unsupportedComposition) return `${unsupportedComposition} is not supported.`;

  const types = typeof node['type'] === 'string'
    ? [node['type']]
    : Array.isArray(node['type']) && node['type'].every((item) => typeof item === 'string')
      ? node['type'] as string[]
      : [];
  if (!types.length || types.some((type) => !SUPPORTED_SCHEMA_TYPES.has(type))) {
    return `${path} must define a supported JSON type.`;
  }

  const primaryType = types.find((type) => type !== 'null') ?? 'null';
  if (primaryType === 'object') {
    const properties = node['properties'];
    if (!properties || typeof properties !== 'object' || Array.isArray(properties)) {
      return `${path} must contain a non-empty properties object.`;
    }
    const entries = Object.entries(properties);
    if (!entries.length) return `${path} must contain at least one property.`;
    if (entries.length > 100) return `${path} cannot contain more than 100 properties.`;
    for (const [name, child] of entries) {
      const error = validateSchemaNode(child, `${path}.properties.${name}`, depth + 1);
      if (error) return error;
    }
  } else if (primaryType === 'array' && node['items'] !== undefined) {
    return validateSchemaNode(node['items'], `${path}.items`, depth + 1);
  }
  return null;
}

export type FieldType = 'text' | 'number' | 'boolean' | 'list';

export interface SchemaField {
  name: string;
  type: FieldType;
}

export const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'boolean', label: 'Yes / No' },
  { value: 'list', label: 'List of text' },
];

export function buildSchemaFromFields(fields: SchemaField[]): string {
  const properties: Record<string, unknown> = {};
  for (const field of fields) {
    const name = field.name.trim();
    if (!name) continue;
    properties[name] =
      field.type === 'number'
        ? { type: 'number' }
        : field.type === 'boolean'
          ? { type: 'boolean' }
          : field.type === 'list'
            ? { type: 'array', items: { type: 'string' } }
            : { type: 'string' };
  }
  if (!Object.keys(properties).length) return '';
  return JSON.stringify({ type: 'object', properties }, null, 2);
}

export function validateJsonSchema(raw: string): string | null {
  if (!raw.trim()) return 'JSON Schema is required.';
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return 'Invalid JSON. Enter a valid JSON Schema.';
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return 'JSON Schema must be an object.';
  }
  const root = value as Record<string, unknown>;
  if (root['type'] !== 'object') return 'Root type must be "object".';
  return validateSchemaNode(root, 'Root schema', 0);
}

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit, OnDestroy {
  private readonly http = inject(HttpClient);
  private pollTimer?: ReturnType<typeof setInterval>;
  private pollingExtractionIds = new Set<string>();

  readonly health = signal<HealthResponse | null>(null);
  readonly healthLoading = signal(true);
  readonly healthError = signal(false);
  readonly selectedFiles = signal<File[]>([]);
  readonly selectedFile = computed(() => this.selectedFiles()[0] ?? null);
  readonly fileRejections = signal<BatchRejection[]>([]);
  readonly isDragging = signal(false);
  readonly submitting = signal(false);
  readonly uploadProgress = signal(0);
  readonly activeJob = signal<PdfJob | null>(null);
  readonly activeTab = signal<ResultTab>('data');
  readonly copied = signal(false);
  readonly batchSummary = signal<BatchResponse | null>(null);
  readonly batchJobs = signal<PdfJob[]>([]);
  readonly batchCopied = signal(false);
  readonly inputMode = signal<'simple' | 'advanced'>('advanced');
  readonly fields = signal<SchemaField[]>([{ name: '', type: 'text' }]);
  readonly setupOpen = signal(true);
  readonly expandedJobId = signal<string | null>(null);
  readonly copiedJobId = signal<string | null>(null);
  readonly fieldTypes = FIELD_TYPES;
  readonly apiKey = signal(readStoredApiKey());
  readonly apiKeyDraft = signal('');
  readonly unauthorized = signal(false);

  outputTemplate = '';
  schemaError = '';
  ocrMode: OcrMode = 'auto';
  submitError = '';

  readonly totalFileBytes = computed(() => this.selectedFiles().reduce((total, file) => total + file.size, 0));
  readonly maxBatchFiles = computed(() => this.health()?.max_batch_files ?? DEFAULT_MAX_BATCH_FILES);
  readonly maxBatchBytes = computed(() => (this.health()?.max_batch_total_mb ?? DEFAULT_MAX_BATCH_BYTES / 1024 / 1024) * 1024 * 1024);
  schemaChecks(): { validJson: boolean; rootObject: boolean; properties: boolean; supported: boolean } {
    const error = validateJsonSchema(this.outputTemplate);
    let parsed: Record<string, unknown> | null = null;
    try { parsed = JSON.parse(this.outputTemplate) as Record<string, unknown>; } catch { /* validation reports this */ }
    return {
      validJson: !!this.outputTemplate.trim() && !!parsed,
      rootObject: !!parsed && !Array.isArray(parsed) && parsed['type'] === 'object',
      properties: !!parsed && !!parsed['properties'] && typeof parsed['properties'] === 'object' && !Array.isArray(parsed['properties']) && Object.keys(parsed['properties'] as object).length > 0,
      supported: !!this.outputTemplate.trim() && error === null,
    };
  }

  needsApiKey(): boolean {
    return (!!this.health()?.require_api_key && !this.apiKey()) || this.unauthorized();
  }

  saveApiKey(): void {
    const key = this.apiKeyDraft().trim();
    if (!key) return;
    storeApiKey(key);
    this.apiKey.set(key);
    this.apiKeyDraft.set('');
    this.unauthorized.set(false);
    this.loadHealth();
  }

  clearApiKey(): void {
    storeApiKey('');
    this.apiKey.set('');
    this.batchJobs.set([]);
    this.activeJob.set(null);
    this.unauthorized.set(false);
  }

  maskedApiKey(): string {
    const key = this.apiKey();
    return key ? `${key.slice(0, 14)}…` : '';
  }

  canSubmit(): boolean {
    return (
      !!this.health()?.ai_configured &&
      this.selectedFiles().length > 0 &&
      validateJsonSchema(this.outputTemplate) === null &&
      !this.submitting()
    );
  }

  readonly displayResult = computed(() => this.resultData(this.activeJob()));

  readonly batchFinishedCount = computed(
    () => this.batchJobs().filter((job) => job.status === 'completed' || job.status === 'failed').length,
  );

  /** Every job the results table shows: the whole batch, or a single reopened job. */
  readonly tableJobs = computed(() => {
    const batch = this.batchJobs();
    if (batch.length) return batch;
    const single = this.activeJob();
    return single ? [single] : [];
  });

  readonly finishedCount = computed(
    () => this.tableJobs().filter((job) => job.status === 'completed' || job.status === 'failed').length,
  );

  /** Column order comes from the schema, then from anything extra a result returned. */
  columns(): string[] {
    const names: string[] = [];
    const add = (name: string) => {
      if (!names.includes(name)) names.push(name);
    };
    this.schemaFieldNames().forEach(add);
    for (const job of this.tableJobs()) {
      const data = this.resultData(job);
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        Object.keys(data as Record<string, unknown>).forEach(add);
      }
    }
    return names;
  }

  readonly batchCombined = computed(() =>
    this.batchJobs().map((job) => ({
      file: this.filename(job),
      job_id: job.id,
      status: job.status,
      data: job.status === 'completed' ? this.resultData(job) : null,
      error: job.error ?? null,
    })),
  );

  readonly evidence = computed(() => {
    const result = this.activeJob()?.result;
    return result && typeof result === 'object' && Array.isArray((result as JobResult).evidence)
      ? (result as JobResult).evidence!
      : [];
  });

  ngOnInit(): void {
    this.loadHealth();
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  loadHealth(): void {
    this.healthLoading.set(true);
    this.healthError.set(false);
    this.http.get<HealthResponse>('/api/health').subscribe({
      next: (health) => {
        this.health.set(health);
        this.healthLoading.set(false);
      },
      error: () => {
        this.healthError.set(true);
        this.healthLoading.set(false);
      },
    });
  }

  onFileInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.addFiles(input.files);
    input.value = '';
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(false);
    this.addFiles(event.dataTransfer?.files);
  }

  selectFile(file: File): void {
    this.addFiles([file]);
  }

  addFiles(fileList: FileList | File[] | null | undefined): void {
    if (!fileList?.length) return;
    const accepted = [...this.selectedFiles()];
    const rejected: BatchRejection[] = [];
    const fileLimit = (this.health()?.max_upload_mb ?? MAX_FILE_BYTES / 1024 / 1024) * 1024 * 1024;
    for (const file of Array.from(fileList)) {
      const basicError = validatePdfFile(file, fileLimit);
      const duplicate = accepted.some((item) => item.name.toLowerCase() === file.name.toLowerCase() && item.size === file.size);
      const tooMany = accepted.length >= this.maxBatchFiles();
      const tooLarge = this.totalBytes(accepted) + file.size > this.maxBatchBytes();
      const error = basicError ?? (duplicate ? 'This PDF is already in the batch.' : null) ?? (tooMany ? `Batch limit is ${this.maxBatchFiles()} files.` : null) ?? (tooLarge ? `Batch total cannot exceed ${this.humanSize(this.maxBatchBytes())}.` : null);
      if (error) rejected.push({ file_name: file.name, error });
      else accepted.push(file);
    }
    this.selectedFiles.set(accepted);
    if (rejected.length) this.fileRejections.update((items) => [...rejected, ...items].slice(0, 20));
    this.submitError = '';
  }

  removeFile(file: File, event?: Event): void {
    event?.stopPropagation();
    this.selectedFiles.update((files) => files.filter((item) => item !== file));
  }

  clearFiles(event?: Event): void {
    event?.stopPropagation();
    this.selectedFiles.set([]);
    this.fileRejections.set([]);
  }

  validateSchemaInput(): void {
    this.schemaError = validateJsonSchema(this.outputTemplate) ?? '';
    this.submitError = '';
  }

  submit(): void {
    this.schemaError = validateJsonSchema(this.outputTemplate) ?? '';
    if (!this.canSubmit()) return;
    const data = new FormData();
    this.selectedFiles().forEach((file) => data.append('files', file));
    data.append('output_template', this.outputTemplate.trim());
    data.append('ocr_mode', this.ocrMode);

    this.submitError = '';
    this.submitting.set(true);
    this.uploadProgress.set(0);
    const request = new HttpRequest('POST', '/api/v1/extractions', data, { reportProgress: true });
    this.http.request<BatchResponse>(request).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.uploadProgress.set(Math.round((event.loaded / event.total) * 100));
        }
        if (event.type === HttpEventType.Response && event.body) {
          this.submitting.set(false);
          this.uploadProgress.set(100);
          const batch = event.body;
          this.batchSummary.set(batch);
          this.selectedFiles.set([]);
          this.fileRejections.set([]);
          this.uploadProgress.set(0);
          this.batchJobs.update((jobs) => [
            ...jobs.filter((job) => !batch.jobs.some((added) => added.id === job.id)),
            ...batch.jobs,
          ]);
          if (batch.jobs.length) {
            this.setupOpen.set(false);
            if (!this.isRunning(this.activeJob())) this.activeJob.set(batch.jobs[0]);
            if (batch.extraction_id) this.startPolling(batch.extraction_id);
          }
        }
      },
      error: (error) => {
        this.submitting.set(false);
        this.submitError = this.apiError(error, 'We could not start this extraction. Please try again.');
      },
    });
  }

  isRunning(job: PdfJob | null | undefined): boolean {
    return job?.status === 'queued' || job?.status === 'processing';
  }

  startNew(): void {
    this.stopPolling();
    this.activeJob.set(null);
    this.selectedFiles.set([]);
    this.fileRejections.set([]);
    this.batchSummary.set(null);
    this.batchJobs.set([]);
    this.outputTemplate = '';
    this.schemaError = '';
    this.ocrMode = 'auto';
    this.uploadProgress.set(0);
    this.submitError = '';
    this.activeTab.set('data');
    this.inputMode.set('advanced');
    this.fields.set([{ name: '', type: 'text' }]);
    this.setupOpen.set(true);
    this.expandedJobId.set(null);
  }

  retryCurrent(): void {
    this.activeJob.set(null);
    this.submitError = '';
  }

  copyJson(): void {
    navigator.clipboard.writeText(this.prettyJson(this.activeJob()?.result ?? {})).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1800);
    });
  }

  schemaFieldNames(): string[] {
    try {
      const parsed = JSON.parse(this.outputTemplate) as Record<string, unknown>;
      const properties = parsed?.['properties'];
      if (properties && typeof properties === 'object' && !Array.isArray(properties)) {
        return Object.keys(properties as Record<string, unknown>);
      }
    } catch {
      /* an incomplete schema simply contributes no columns yet */
    }
    return [];
  }

  addField(): void {
    this.fields.update((fields) => [...fields, { name: '', type: 'text' as FieldType }]);
    this.syncFields();
  }

  removeField(index: number): void {
    this.fields.update((fields) => (fields.length > 1 ? fields.filter((_, at) => at !== index) : fields));
    this.syncFields();
  }

  updateFieldName(index: number, name: string): void {
    this.fields.update((fields) => fields.map((field, at) => (at === index ? { ...field, name } : field)));
    this.syncFields();
  }

  updateFieldType(index: number, type: FieldType): void {
    this.fields.update((fields) => fields.map((field, at) => (at === index ? { ...field, type } : field)));
    this.syncFields();
  }

  /** The field rows are just a friendly editor for the JSON Schema the API needs. */
  syncFields(): void {
    this.outputTemplate = buildSchemaFromFields(this.fields());
    this.schemaError = this.outputTemplate ? (validateJsonSchema(this.outputTemplate) ?? '') : '';
    this.submitError = '';
  }

  useSimpleFields(): void {
    this.inputMode.set('simple');
    this.syncFields();
  }

  useJsonSchema(): void {
    this.inputMode.set('advanced');
    this.schemaError = this.outputTemplate.trim() ? (validateJsonSchema(this.outputTemplate) ?? '') : '';
  }

  toggleDetails(job: PdfJob): void {
    this.expandedJobId.update((current) => (current === job.id ? null : job.id));
    if (this.expandedJobId() === job.id) this.activeJob.set(job);
  }

  cellValue(job: PdfJob, column: string): string {
    if (job.status !== 'completed') return '';
    const data = this.resultData(job);
    if (!data || typeof data !== 'object' || Array.isArray(data)) return '—';
    const value = (data as Record<string, unknown>)[column];
    if (value === null || value === undefined || value === '') return '—';
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  evidenceFor(job: PdfJob): EvidenceItem[] {
    const result = job.result;
    return result && typeof result === 'object' && Array.isArray((result as JobResult).evidence)
      ? (result as JobResult).evidence!
      : [];
  }

  statusLabel(job: PdfJob): string {
    if (job.status === 'completed') return 'Done';
    if (job.status === 'failed') return 'Failed';
    if (job.status === 'queued') return 'Waiting';
    return `${job.progress ?? 0}%`;
  }

  downloadCsv(): void {
    const columns = this.columns();
    const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
    const rows = [
      ['File', ...columns, 'Status'].map(escape).join(','),
      ...this.tableJobs().map((job) =>
        [this.filename(job), ...columns.map((column) => this.cellValue(job, column)), this.statusLabel(job)]
          .map(escape)
          .join(','),
      ),
    ];
    const csv = rows.join('\r\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `extraction-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  copyJobJson(job: PdfJob): void {
    navigator.clipboard.writeText(this.prettyJson(this.resultData(job))).then(() => {
      this.copiedJobId.set(job.id);
      setTimeout(() => this.copiedJobId.update((id) => (id === job.id ? null : id)), 1800);
    });
  }

  copyBatchJson(): void {
    navigator.clipboard.writeText(this.prettyJson(this.batchCombined())).then(() => {
      this.batchCopied.set(true);
      setTimeout(() => this.batchCopied.set(false), 1800);
    });
  }

  resultData(job: PdfJob | null | undefined): unknown {
    const result = job?.result;
    if (!result || typeof result !== 'object') return result ?? {};
    const typed = result as JobResult;
    return typed.structured_data ?? typed.data ?? result;
  }

  resultFields(job: PdfJob): { key: string; value: string }[] {
    const data = this.resultData(job);
    if (!data || typeof data !== 'object' || Array.isArray(data)) return [];
    return Object.entries(data as Record<string, unknown>).map(([key, value]) => ({
      key,
      value:
        value === null || value === undefined
          ? '—'
          : typeof value === 'object'
            ? JSON.stringify(value)
            : String(value),
    }));
  }

  prettyJson(value: unknown): string {
    return JSON.stringify(value ?? {}, null, 2);
  }

  humanSize(bytes: number): string {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  duration(job: PdfJob): string {
    if (job.duration_ms == null) return job.status === 'completed' || job.status === 'failed' ? 'Not recorded' : 'In progress';
    if (job.duration_ms < 1000) return `${job.duration_ms} ms`;
    const seconds = job.duration_ms / 1000;
    return seconds < 60 ? `${seconds.toFixed(1)} s` : `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  }

  ocrCoverage(job: PdfJob): number {
    if (!job.page_count) return 0;
    return Math.round(((job.ocr_pages ?? 0) / job.page_count) * 100);
  }

  pythonPages(job: PdfJob): number | null {
    if (job.python_text_pages != null) return job.python_text_pages;
    if (job.page_count != null) return Math.max(0, job.page_count - (job.ocr_pages ?? 0));
    return null;
  }

  ocrModel(job: PdfJob): string {
    return (job.ocr_pages ?? 0) > 0 ? (job.ocr_model || this.health()?.ocr_model || 'Unknown') : 'Not used';
  }

  visionModel(job: PdfJob): string {
    return (job.vision_attempted_pages ?? 0) > 0
      ? (job.vision_model || this.health()?.vision_model || 'Unknown')
      : 'Not used';
  }

  visionPages(job: PdfJob): number {
    return job.vision_pages ?? 0;
  }

  routeSummary(job: PdfJob): string {
    const python = this.pythonPages(job);
    return `P ${python ?? '—'} / V ${this.visionPages(job)} / O ${job.ocr_pages ?? 0}`;
  }

  processingStep(job: PdfJob): number {
    const stage = (job.stage ?? '').toLowerCase();
    if (job.status === 'completed' || stage.includes('validat') || stage.includes('completed')) return 6;
    if (stage.includes('extract') || stage.includes('section') || stage.includes('chunk')) return 5;
    if (stage.includes('ocr')) return 4;
    if (stage.includes('vision')) return 3;
    if (stage.includes('read') || stage.includes('python') || stage.includes('page text')) return 2;
    if (stage.includes('upload') || job.status === 'queued') return 1;
    const progress = job.progress ?? 0;
    if (progress >= 82) return 6;
    if (progress >= 58) return 5;
    if (progress >= 38) return 4;
    if (progress >= 18) return 3;
    if (progress >= 5) return 2;
    return 1;
  }

  readingRouteWasUsed(job: PdfJob, route: ReadingRoute): boolean {
    if (route === 'python') {
      if (job.python_text_pages != null) return job.python_text_pages > 0;
      return (this.pythonPages(job) ?? 0) > 0;
    }
    if (route === 'vision') return (job.vision_attempted_pages ?? 0) > 0;
    return (job.ocr_pages ?? 0) > 0;
  }

  readingRouteIsDone(job: PdfJob, route: ReadingRoute): boolean {
    const routeStep = route === 'python' ? 2 : route === 'vision' ? 3 : 4;
    return this.processingStep(job) > routeStep && this.readingRouteWasUsed(job, route);
  }

  readingRouteWasSkipped(job: PdfJob, route: ReadingRoute): boolean {
    const routeStep = route === 'python' ? 2 : route === 'vision' ? 3 : 4;
    return this.processingStep(job) > routeStep && !this.readingRouteWasUsed(job, route);
  }

  readingRouteLabel(job: PdfJob, route: ReadingRoute): string {
    const routeStep = route === 'python' ? 2 : route === 'vision' ? 3 : 4;
    if (this.processingStep(job) <= routeStep) {
      return route === 'python' ? 'Native text' : route === 'vision' ? 'Unreadable pages' : 'Vision misses';
    }
    if (!this.readingRouteWasUsed(job, route)) return route === 'python' ? 'No native text' : 'Not needed';

    const pages = route === 'python'
      ? (this.pythonPages(job) ?? 0)
      : route === 'vision'
        ? (job.vision_attempted_pages ?? 0)
        : (job.ocr_pages ?? 0);
    return `${pages} page${pages === 1 ? '' : 's'} ${route === 'vision' ? 'tried' : 'used'}`;
  }

  schemaMode(job: PdfJob): string {
    return job.schema_mode && job.schema_mode !== 'none' ? job.schema_mode.replace('_', ' ') : 'none';
  }

  retryGuidance(job: PdfJob): string {
    // Say what to do next. A rate limit needs waiting, bad credentials need the
    // operator, a page-limit rejection needs a different file.
    switch (job.failure_code) {
      case 'AI_RATE_LIMITED':
        return 'The AI provider is rate limiting this service. Nothing is wrong with your file — wait a few minutes and submit it again.';
      case 'AI_AUTH_FAILED':
        return 'The service could not authenticate with its AI provider. This is a server configuration problem, not something you can fix here — contact whoever runs this service.';
      case 'AI_PROVIDER_UNAVAILABLE':
        return 'The AI provider is having an outage. Try again in a few minutes.';
      case 'AI_TIMEOUT':
        return 'The AI provider did not respond in time. Try again; if it repeats, try a smaller PDF.';
    }
    if (job.failure_code === 'PDF_PAGE_LIMIT_EXCEEDED' || job.error?.toLowerCase().includes('maximum allowed')) {
      return `Split the PDF into files of ${this.health()?.max_pdf_pages ?? 40} pages or fewer, then submit again.`;
    }
    if (job.failure_stage === 'OCR') return 'Retry with OCR set to Auto, or use a clearer scan. If it repeats, verify the OCR model and API key.';
    if (job.failure_stage === 'Structured extraction') return 'Check that the input is a valid JSON Schema, then retry.';
    return 'Review the error and input settings, then retry. If it repeats, check the backend log using this job ID.';
  }

  contractLabel(job: PdfJob): string {
    if (job.schema_mode === 'json_schema') return 'JSON Schema';
    return 'JSON Schema';
  }

  private apiError(error: any, fallback: string): string {
    if (error?.status === 401) {
      this.unauthorized.set(true);
      return 'This API key was rejected. Enter a valid key to continue.';
    }
    const detail = error?.error?.detail ?? error?.error?.message;
    if (Array.isArray(detail)) return detail.map((item) => item?.msg ?? String(item)).join(' ');
    return typeof detail === 'string' && detail.trim() ? detail : fallback;
  }

  filename(job: PdfJob): string {
    return job.filename ?? job.file_name ?? 'PDF document';
  }

  formatTime(value?: string): string {
    if (!value) return 'Just now';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
  }

  evidencePage(item: EvidenceItem): string {
    return String(item.page ?? item.page_number ?? '—');
  }

  evidenceText(item: EvidenceItem): string {
    return String(item.evidence ?? item.quote ?? item.text ?? JSON.stringify(item));
  }

  private totalBytes(files: File[]): number {
    return files.reduce((total, file) => total + file.size, 0);
  }

  /** One request returns every document in an extraction, so poll per extraction. */
  private startPolling(extractionId: string): void {
    this.pollingExtractionIds.add(extractionId);
    if (!this.pollTimer) {
      this.pollTimer = setInterval(() => this.refreshExtractions(), 1500);
    }
    this.refreshExtractions();
  }

  private refreshExtractions(): void {
    for (const id of [...this.pollingExtractionIds]) {
      this.http.get<PdfJob[]>(`/api/v1/extractions/${id}`).subscribe({
        next: (jobs) => {
          // Merge, never replace: a second submission runs alongside the first,
          // and its documents are appended below the ones already on the board.
          this.batchJobs.update((current) => {
            const fresh = new Map(jobs.map((job) => [job.id, job]));
            const updated = current.map((job) => fresh.get(job.id) ?? job);
            const known = new Set(updated.map((job) => job.id));
            return [...updated, ...jobs.filter((job) => !known.has(job.id))];
          });

          const active = this.activeJob();
          if (active) {
            const refreshed = jobs.find((job) => job.id === active.id);
            if (refreshed) this.activeJob.set(refreshed);
          }

          if (jobs.every((job) => !this.isRunning(job))) this.finishPolling(id);
        },
        error: (error) => {
          if (error?.status === 401) this.unauthorized.set(true);
          this.finishPolling(id);
        },
      });
    }
  }

  private finishPolling(extractionId: string): void {
    this.pollingExtractionIds.delete(extractionId);
    if (!this.pollingExtractionIds.size) this.stopPolling();
  }

  private stopPolling(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = undefined;
    this.pollingExtractionIds.clear();
  }
}
