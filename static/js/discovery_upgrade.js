/* Customer favorites and on-page compare. No server writes and no payment changes. */
(() => {
  'use strict';
  const container = document.querySelector('[data-pvc-discovery]');
  if (!container) return;

  const key = `pharmacityville:favorites:v1:${container.dataset.favoritesKey || 'guest'}`;
  const cards = [...document.querySelectorAll('[data-pvc-product-card]')];
  const compareIds = new Set();
  const favoriteIds = new Set();
  const favOnly = document.getElementById('pvc-favorites-only');
  const favoritesCount = document.getElementById('pvc-favorite-count');
  const shownCount = document.getElementById('pvc-filtered-count');
  const compareCount = document.getElementById('pvc-compare-count');
  const compareButton = document.getElementById('pvc-compare-open');
  const compareClear = document.getElementById('pvc-compare-clear');
  const compareFeedback = document.getElementById('pvc-compare-feedback');
  const compareModal = document.getElementById('pvc-compare-modal');
  const compareTable = document.getElementById('pvc-compare-table');
  let storageAvailable = true;

  try {
    const values = JSON.parse(localStorage.getItem(key) || '[]');
    if (Array.isArray(values)) {
      for (const item of values.slice(0, 100)) {
        if (/^[1-9]\d*$/.test(String(item))) favoriteIds.add(String(item));
      }
    }
  } catch (error) { storageAvailable = false; }

  const map = new Map(cards.map(card => [card.dataset.medicineId, card]));

  function announce(message) {
    if (compareFeedback) compareFeedback.textContent = message;
  }
  function saveFavorites() {
    try { localStorage.setItem(key, JSON.stringify([...favoriteIds])); }
    catch (error) { storageAvailable = false; announce('Favorites are available only for this visit; your browser prevented saving.'); }
  }
  function refresh() {
    let visible = 0;
    for (const card of cards) {
      const id = card.dataset.medicineId;
      const isFavorite = favoriteIds.has(id);
      const isCompare = compareIds.has(id);
      card.hidden = Boolean(favOnly?.checked) && !isFavorite;
      // Never leave hidden medicines checked for the add-to-cart form.
      if (card.hidden) {
        const selectedForCart = card.querySelector('[data-pvc-medicine-checkbox]');
        if (selectedForCart?.checked) {
          selectedForCart.checked = false;
          selectedForCart.dispatchEvent(new Event('change', {bubbles:true}));
        }
      }
      if (!card.hidden) visible++;
      const heart = card.querySelector('[data-pvc-favorite]');
      if (heart) {
        heart.setAttribute('aria-pressed', String(isFavorite));
        heart.setAttribute('aria-label', `${isFavorite ? 'Remove' : 'Add'} ${card.dataset.medicineName} ${isFavorite ? 'from' : 'to'} favorites`);
        heart.title = isFavorite ? 'Remove from favorites' : 'Save to favorites';
        heart.classList.toggle('pvc-is-favorite', isFavorite);
        const icon = heart.querySelector('i');
        if (icon) icon.className = isFavorite ? 'bi bi-heart-fill' : 'bi bi-heart';
      }
      const compare = card.querySelector('[data-pvc-compare]');
      if (compare) {
        compare.setAttribute('aria-pressed', String(isCompare));
        compare.classList.toggle('pvc-is-comparing', isCompare);
        compare.textContent = isCompare ? 'Selected to compare' : 'Compare';
      }
    }
    if (favoritesCount) favoritesCount.textContent = `${favoriteIds.size} saved`;
    if (shownCount) shownCount.textContent = `${visible} shown in current results`;
    if (compareCount) compareCount.textContent = `${compareIds.size} of 3 chosen`;
    if (compareButton) compareButton.disabled = compareIds.size < 2;
    if (compareClear) compareClear.disabled = compareIds.size === 0;
    document.getElementById('pvc-no-favorites')?.classList.toggle('d-none', visible !== 0 || !favOnly?.checked);
  }

  container.addEventListener('change', event => {
    if (event.target === favOnly) refresh();
  });
  document.addEventListener('click', event => {
    const heart = event.target.closest?.('[data-pvc-favorite]');
    if (heart) {
      const id = heart.dataset.pvcFavorite;
      if (favoriteIds.has(id)) favoriteIds.delete(id);
      else if (favoriteIds.size < 100) favoriteIds.add(id);
      else { announce('You can save up to 100 favorites on this browser.'); return; }
      saveFavorites();
      refresh();
      announce(`${map.get(id)?.dataset.medicineName || 'Medicine'} ${favoriteIds.has(id) ? 'saved to' : 'removed from'} favorites.`);
      return;
    }
    const compare = event.target.closest?.('[data-pvc-compare]');
    if (compare) {
      const id = compare.dataset.pvcCompare;
      if (compareIds.has(id)) compareIds.delete(id);
      else if (compareIds.size < 3) compareIds.add(id);
      else { announce('Compare up to three medicines at once.'); return; }
      refresh();
    }
  });

  compareClear?.addEventListener('click', () => {
    compareIds.clear(); refresh(); announce('Comparison cleared.');
  });

  const rows = [
    ['Category', 'medicineCategory'],
    ['Price per unit', 'medicinePrice'],
    ['Available stock', 'medicineStock'],
    ['Prescription', 'medicineRx'],
    ['Description', 'medicineDescription'],
  ];
  compareButton?.addEventListener('click', () => {
    if (compareIds.size < 2 || !compareTable || !compareModal) return;
    compareTable.replaceChildren();
    const table = document.createElement('table');
    table.className = 'table table-bordered table-striped align-middle mb-0';
    const thead = table.createTHead();
    const tr = thead.insertRow();
    const first = document.createElement('th'); first.textContent = 'Detail'; first.scope = 'col'; tr.append(first);
    const selected = [...compareIds].map(id => map.get(id)).filter(Boolean);
    for (const card of selected) {
      const th = document.createElement('th'); th.scope = 'col'; th.textContent = card.dataset.medicineName || '';
      tr.append(th);
    }
    const tbody = table.createTBody();
    for (const [label, prop] of rows) {
      const row = tbody.insertRow();
      const heading = document.createElement('th'); heading.scope = 'row'; heading.textContent = label; row.append(heading);
      for (const card of selected) {
        const td = row.insertCell();
        td.textContent = prop === 'medicineRx' ? (card.dataset.medicineRx === 'yes' ? 'Approval required' : 'Not marked prescription-required') : (card.dataset[prop] || '—');
      }
    }
    compareTable.append(table);
    if (window.bootstrap?.Modal) window.bootstrap.Modal.getOrCreateInstance(compareModal).show();
    else announce('The comparison dialog could not open. Refresh the page and try again.');
  });
  if (!storageAvailable) announce('Your browser may not keep favorites after you leave.');
  refresh();
})();
