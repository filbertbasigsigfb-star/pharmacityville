/* Pharmacityville final features: read-only convenience UX, no API or database writes. */
(() => {
  'use strict';
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const norm = (s) => String(s || '').trim().toLocaleLowerCase();
  function safeStoreRead(key) {
    try { const v = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(v) ? v : []; }
    catch (_) { return []; }
  }
  function safeStoreWrite(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {} }
  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // 1: instant search of currently loaded catalog results.
  // 2: complete-description Quick View dialog (does not buy/add medicines).
  // 3: locally saved recently viewed medicines, per account/browser.
  function catalog() {
    const wrap = $('[data-pvc-final-catalog]');
    if (!wrap) return;
    const query = $('#pvc-final-live-search');
    const label = $('#pvc-final-live-count');
    const recent = $('#pvc-final-recent');
    const userKey = wrap.dataset.userKey || 'guest';
    const recentKey = `pvc:recently-viewed:v1:${userKey}`;
    const cards = $$('.medicine-image').map(img => img.closest('.col')).filter(Boolean);
    const modal = $('#pvc-final-quick-modal');
    const modalName = $('#pvc-final-quick-name');
    const modalImage = $('#pvc-final-quick-image');
    const modalDetails = $('#pvc-final-quick-details');
    const cardMeta = card => ({
      name: $('h2.h5', card)?.textContent?.trim() || '',
      category: $('.card-body > p.small.text-muted', card)?.textContent?.trim() || '',
      image: $('.medicine-image', card)?.getAttribute('src') || '',
    });

    function updateLiveSearch() {
      let shown = 0;
      const word = norm(query?.value);
      cards.forEach(card => {
        const searchable = [cardMeta(card).name, cardMeta(card).category, $('.pvc-final-quick-view', card)?.dataset.description || ''].join(' ');
        const exclude = word && !norm(searchable).includes(word);
        card.classList.toggle('pvc-final-search-hidden', Boolean(exclude));
        if (exclude) {
          // Hidden products must never be accidentally submitted to checkout.
          const cb = $('input[name="medicine_ids"]', card);
          if (cb?.checked) { cb.checked = false; cb.dispatchEvent(new Event('change', {bubbles:true})); }
        }
        if (!exclude && !card.hidden) shown++;
      });
      if (label) label.textContent = `${shown} matching currently loaded medicines`;
    }
    query?.addEventListener('input', updateLiveSearch);
    query?.addEventListener('keydown', e => { if (e.key === 'Escape') { query.value = ''; updateLiveSearch(); } });
    // Slash focuses the catalog search unless the user is typing in a field.
    document.addEventListener('keydown', e => {
      if (e.key !== '/' || e.altKey || e.ctrlKey || e.metaKey) return;
      if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable) return;
      e.preventDefault(); query?.focus();
    });

    const readRecent = () => safeStoreRead(recentKey).filter(item => item && /^\d+$/.test(String(item.id)) && typeof item.name === 'string').slice(0, 8);
    function recentRender() {
      if (!recent) return;
      recent.replaceChildren();
      const items = readRecent();
      if (!items.length) { recent.append(make('span', 'small text-muted', 'No medicines viewed yet.')); return; }
      items.forEach(item => {
        const link = make('a', 'pvc-final-recent-link', item.name.slice(0, 90));
        // A fresh catalog GET for medicine name, even across server-side filters.
        link.href = `${wrap.dataset.catalogUrl}?${new URLSearchParams({search:item.name})}`;
        link.title = `Find ${item.name} in the catalog`;
        recent.append(link);
      });
    }
    function markRecent(id, name) {
      const current = readRecent().filter(v => String(v.id) !== String(id));
      current.unshift({id: String(id), name: name.slice(0, 120)});
      safeStoreWrite(recentKey, current.slice(0, 8)); recentRender();
    }
    function quickView(button, card) {
      if (!modal || !window.bootstrap?.Modal) return;
      const data = cardMeta(card);
      if (!data.name) return;
      if (modalName) modalName.textContent = data.name;
      if (modalImage) { modalImage.src = data.image; modalImage.alt = `Catalog image for ${data.name}`; }
      if (modalDetails) {
        modalDetails.replaceChildren();
        const rows = [
          ['Category', data.category],
          ['Price', button.dataset.price],
          ['Available stock', button.dataset.stock],
          ['Prescription', button.dataset.rx === 'yes' ? 'Approval required' : 'Not marked prescription-required'],
          ['Description', button.dataset.description || 'No description provided'],
        ];
        rows.forEach(([label, value]) => {
          const line = make('p', 'mb-2');
          line.append(make('strong', '', `${label}: `), document.createTextNode(value || '—'));
          modalDetails.append(line);
        });
      }
      markRecent(button.dataset.id, data.name);
      window.bootstrap.Modal.getOrCreateInstance(modal).show();
    }
    document.addEventListener('click', event => {
      const button = event.target.closest?.('.pvc-final-quick-view');
      if (button) { const card = button.closest('.col'); if (card) quickView(button, card); }
    });
    $('#pvc-final-clear-recent')?.addEventListener('click', () => {
      safeStoreWrite(recentKey, []); recentRender();
    });
    recentRender(); updateLiveSearch();
  }

  // 4: accessible plus/minus cart quantity with explicit server-side Update.
  function cart() {
    $$('input.cart-quantity').forEach(input => {
      if (input.dataset.finalReady) return;
      input.dataset.finalReady = '1';
      const wrapper = make('div', 'pvc-final-cart-counter');
      const minus = make('button', 'btn btn-outline-secondary btn-sm pvc-final-step', '−');
      const plus = make('button', 'btn btn-outline-secondary btn-sm pvc-final-step', '+');
      minus.type = plus.type = 'button';
      minus.setAttribute('aria-label', 'Decrease quantity');
      plus.setAttribute('aria-label', 'Increase quantity');
      input.parentNode.insertBefore(wrapper, input);
      wrapper.append(minus, input, plus);
      const hint = make('span', 'pvc-final-cart-hint', 'Click Update to save changes.');
      wrapper.after(hint);
      const min = () => Number(input.min) || 1;
      const max = () => Number(input.max) || 999;
      function change(step) {
        const old = Number(input.value) || min();
        input.value = String(Math.min(max(), Math.max(min(), old + step)));
        input.dispatchEvent(new Event('input', {bubbles:true}));
      }
      minus.addEventListener('click', () => change(-1));
      plus.addEventListener('click', () => change(1));
      const check = () => {
        const number = Number(input.value);
        minus.disabled = Number.isFinite(number) && number <= min();
        plus.disabled = Number.isFinite(number) && number >= max();
      };
      input.addEventListener('input', check); check();
    });
  }

  // 5: admin client-only order queue search, status filter, and visible counts.
  // Uses event delegation so automatic live refreshes keep working.
  function adminOrders() {
    const toolbar = $('#pvc-final-order-toolbar');
    if (!toolbar) return;
    let selected = 'All';
    let lastTable = null;
    const input = $('#pvc-final-order-search');
    const count = $('#pvc-final-order-count');
    const buttons = $$('[data-pvc-order-status]', toolbar);
    const statuses = ['All','Pending','Preparing','Ready','Completed','Cancelled'];
    function refresh() {
      const area = $('[data-admin-live-region="orders"]');
      const table = $('table', area || document);
      lastTable = table;
      if (!table) { if (count) count.textContent = '0 orders'; return; }
      const rows = $$('tbody tr', table);
      const searchTerm = norm(input?.value);
      let shown = 0;
      const counts = Object.fromEntries(statuses.map(s => [s, 0]));
      rows.forEach(row => {
        const cells = $$('td', row);
        if (cells.length < 7) return;
        const status = (cells[3].textContent || '').trim();
        counts.All += 1; if (status in counts) counts[status] += 1;
        const matches = norm([cells[0].textContent, cells[1].textContent, cells[3].textContent].join(' ')).includes(searchTerm);
        const visible = matches && (selected === 'All' || selected === status);
        row.classList.toggle('pvc-final-order-hidden', !visible);
        if (visible) shown++;
      });
      buttons.forEach(button => {
        const status = button.dataset.pvcOrderStatus;
        button.classList.toggle('active', status === selected);
        button.setAttribute('aria-pressed', String(status === selected));
        const badge = $('[data-pvc-order-badge]', button);
        if (badge) badge.textContent = String(counts[status] || 0);
      });
      if (count) count.textContent = `${shown} of ${counts.All} orders shown`;
    }
    toolbar.addEventListener('click', event => {
      const btn = event.target.closest?.('[data-pvc-order-status]');
      if (!btn) return;
      selected = btn.dataset.pvcOrderStatus; refresh();
    });
    input?.addEventListener('input', refresh);
    // Replacing the order region after an admin-live response should reapply the filter.
    const workspace = $('.admin-workspace') || document.body;
    const observer = new MutationObserver(records => {
      if (records.some(r => [...r.addedNodes].some(n => n.nodeType === 1 && (n.matches?.('[data-admin-live-region="orders"]') || n.querySelector?.('[data-admin-live-region="orders"]'))))) {
        refresh();
      }
    });
    observer.observe(workspace, {childList:true, subtree:true});
    refresh();
  }

  // 6: editable image URL validation / live image preview (does not modify stored URL).
  // 7: protect admins from losing unsaved medicine form edits.
  function adminMedicineForm() {
    const imageInput = $('#image_url');
    const form = imageInput?.closest('form');
    if (!imageInput || !form || !$('#requires_prescription', form)) return;
    const box = make('div', 'pvc-final-preview');
    const status = make('div', 'pvc-final-preview-status text-muted mb-2', 'Image preview');
    const img = make('img'); img.alt = 'Medicine image preview';
    img.hidden = true;
    box.append(status, img);
    imageInput.closest('.mb-3')?.append(box);
    let timer;
    function preview() {
      clearTimeout(timer);
      const value = imageInput.value.trim();
      img.hidden = true;
      img.removeAttribute('src');
      if (!value) { status.textContent = 'No image specified. A placeholder will appear in the catalog.'; return; }
      if (value.startsWith('/static/svg/')) {
        status.textContent = 'Incorrect folder: use /static/img/medicines/ for locally stored medicine pictures.'; return;
      }
      if (!(value.startsWith('/static/') || /^https:\/\/[^\s]+$/i.test(value))) {
        status.textContent = 'Use /static/img/medicines/filename.webp or a full HTTPS image URL.'; return;
      }
      status.textContent = 'Checking image…';
      timer = setTimeout(() => { img.src = value; }, 250);
    }
    img.addEventListener('load', () => { img.hidden = false; status.textContent = 'Image loaded successfully in this browser.'; });
    img.addEventListener('error', () => { img.hidden = true; status.textContent = 'This image URL could not be loaded. Check the file name and folder before saving.'; });
    imageInput.addEventListener('input', preview); preview();

    const tracked = $$('input[name], textarea[name], select[name]', form).filter(el => el.name !== '_csrf_token');
    const snapshot = () => tracked.map(el => `${el.name}:${el.type === 'checkbox' ? String(el.checked) : el.value}`).join('\u0000');
    const original = snapshot();
    let submitted = false;
    form.addEventListener('submit', () => { submitted = true; });
    window.addEventListener('beforeunload', e => {
      if (!submitted && snapshot() !== original) { e.preventDefault(); e.returnValue = ''; }
    });
  }

  function init() { catalog(); cart(); adminOrders(); adminMedicineForm(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
