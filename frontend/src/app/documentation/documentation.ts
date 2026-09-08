import { Component, computed, effect, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Title, Meta } from '@angular/platform-browser';
import { toSignal } from '@angular/core/rxjs-interop';
import { DOC_PAGES } from './documentation-content';

@Component({
  selector: 'app-documentation',
  imports: [RouterLink],
  templateUrl: './documentation.html',
  styleUrl: './documentation.scss',
  host: { '(document:keydown)': 'onKeydown($event)' },
})
export class Documentation {
  private readonly route = inject(ActivatedRoute);
  private readonly title = inject(Title);
  private readonly meta = inject(Meta);
  private readonly params = toSignal(this.route.paramMap);
  readonly pages = DOC_PAGES;
  readonly query = signal('');
  readonly menuOpen = signal(false);
  readonly copied = signal('');
  readonly copyError = signal('');
  readonly language = signal('cURL');
  readonly activeId = computed(() => this.params()?.get('page') || 'overview');
  readonly current = computed(() => this.pages.find(page => page.id === this.activeId()) || this.pages[0]);
  readonly groups = computed(() => {
    const query = this.query().trim().toLowerCase();
    const matched = this.pages.filter(page => !query || `${page.title} ${page.path || ''} ${page.search}`.toLowerCase().includes(query));
    return [...new Set(matched.map(page => page.group))].map(name => ({ name, pages: matched.filter(page => page.group === name) }));
  });
  readonly headings = computed(() => this.current().blocks.filter(block => block.kind === 'heading'));
  readonly previous = computed(() => this.pages[this.pages.indexOf(this.current()) - 1]);
  readonly next = computed(() => this.pages[this.pages.indexOf(this.current()) + 1]);
  readonly sample = computed(() => this.current().samples?.find(sample => sample.language === this.language()) || this.current().samples?.[0]);

  constructor() {
    effect(() => {
      const page = this.current();
      this.title.setTitle(`${page.title} | PaperSignal documentation`);
      this.meta.updateTag({ name: 'description', content: page.summary });
      this.menuOpen.set(false);
      this.copyError.set('');
      this.query.set('');
    });
  }

  navigate() { this.menuOpen.set(false); }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') this.menuOpen.set(false);
    const target = event.target as HTMLElement | null;
    if (event.key === '/' && !event.ctrlKey && !event.metaKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName || '') && !target?.isContentEditable) {
      event.preventDefault();
      this.menuOpen.set(true);
      setTimeout(() => document.getElementById('docs-search')?.focus());
    }
  }

  async copy(text: string, id: string) {
    try {
      await navigator.clipboard.writeText(text);
      this.copied.set(id);
      this.copyError.set('');
      setTimeout(() => { if (this.copied() === id) this.copied.set(''); }, 2000);
    } catch {
      this.copyError.set('Copy is unavailable in this browser. Select and copy the code directly.');
    }
  }
}
