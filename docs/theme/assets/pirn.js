(function () {
  'use strict';

  // ── Search ──────────────────────────────────────────────────────────────
  const overlay = document.getElementById('search-overlay');
  const modalInput = document.getElementById('search-modal-input');
  const sidebarInput = document.getElementById('search-input');
  const resultsEl = document.getElementById('search-results');
  const closeBtn = document.getElementById('search-close');

  let searchIndex = null;

  function openSearch() {
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    modalInput.focus();
    if (!searchIndex) loadSearchIndex();
  }

  function closeSearch() {
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    modalInput.value = '';
    resultsEl.innerHTML = '<div class="search-hint">Type to search across all pages</div>';
  }

  async function loadSearchIndex() {
    try {
      const base = document.querySelector('base')?.href || '/';
      const r = await fetch(base + 'search/search_index.json');
      const data = await r.json();
      searchIndex = data.docs || [];
    } catch (e) {
      searchIndex = [];
    }
  }

  function doSearch(query) {
    if (!query.trim() || !searchIndex) {
      resultsEl.innerHTML = '<div class="search-hint">Type to search across all pages</div>';
      return;
    }

    const q = query.toLowerCase();
    const matches = searchIndex
      .filter(doc => (doc.title + ' ' + doc.text).toLowerCase().includes(q))
      .slice(0, 12);

    if (!matches.length) {
      resultsEl.innerHTML = '<div class="search-hint">No results found</div>';
      return;
    }

    resultsEl.innerHTML = matches.map(doc => {
      const title = highlight(doc.title || 'Untitled', q);
      const loc = doc.location || '';
      const section = loc.split('/').filter(Boolean).join(' › ') || 'Home';
      return `<a href="${loc}" class="search-result" onclick="closeSearch()">
        <div class="search-result-title">${title}</div>
        <div class="search-result-section">${section}</div>
      </a>`;
    }).join('');
  }

  function highlight(text, q) {
    const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    return text.replace(re, m => `<mark>${m}</mark>`);
  }

  if (overlay) {
    sidebarInput?.addEventListener('focus', openSearch);
    sidebarInput?.addEventListener('click', openSearch);
    closeBtn?.addEventListener('click', closeSearch);
    overlay.addEventListener('click', e => { if (e.target === overlay) closeSearch(); });
    modalInput?.addEventListener('input', e => doSearch(e.target.value));

    document.addEventListener('keydown', e => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); openSearch(); }
      if (e.key === 'Escape' && overlay.classList.contains('open')) closeSearch();
    });
  }

  // ── Mobile sidebar toggle ────────────────────────────────────────────────
  const menuBtn = document.getElementById('menu-toggle');
  const sidebar = document.getElementById('sidebar');

  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });

    document.addEventListener('click', e => {
      if (sidebar.classList.contains('open') &&
          !sidebar.contains(e.target) &&
          !menuBtn.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }

  // ── Active TOC tracking ──────────────────────────────────────────────────
  const tocLinks = document.querySelectorAll('.toc-link');
  if (tocLinks.length) {
    const headings = Array.from(document.querySelectorAll('.content h2, .content h3, .content h4'))
      .filter(h => h.id);

    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        const link = document.querySelector(`.toc-link[href="#${entry.target.id}"]`);
        if (link) link.classList.toggle('active-toc', entry.isIntersecting);
      });
    }, { rootMargin: '-20px 0px -70% 0px' });

    headings.forEach(h => observer.observe(h));
  }

  // ── Code block copy buttons ──────────────────────────────────────────────
  document.querySelectorAll('pre').forEach(pre => {
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.setAttribute('aria-label', 'Copy code');
    btn.innerHTML = '<svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 010 1.5h-1.5a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-1.5a.75.75 0 011.5 0v1.5A1.75 1.75 0 019.25 16h-7.5A1.75 1.75 0 010 14.25v-7.5z"/><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0114.25 11h-7.5A1.75 1.75 0 015 9.25v-7.5zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25h-7.5z"/></svg>';

    btn.addEventListener('click', () => {
      const code = pre.querySelector('code');
      if (code) {
        navigator.clipboard.writeText(code.innerText).then(() => {
          btn.classList.add('copied');
          setTimeout(() => btn.classList.remove('copied'), 1500);
        });
      }
    });

    pre.style.position = 'relative';
    pre.appendChild(btn);
  });
})();
