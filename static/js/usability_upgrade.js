/* Pharmacityville usability upgrade: progressive enhancement only.
 * No payment operations, background writes, APIs or server endpoints are used.
 */
(() => {
  'use strict';
  const catalog = document.getElementById('selected-medicines-form');
  const customerBar = document.getElementById('pvc-floating-cart');
  const adminBar = document.getElementById('pvc-floating-restock');
  const inventoryRegion = document.querySelector('[data-admin-live-region="medicines"]');
  const money = new Intl.NumberFormat('en-PH', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  let lastAnnouncement = '';

  function announce(message) {
    const target = document.getElementById('pvc-live-feedback');
    if (target && message !== lastAnnouncement) { target.textContent = message; lastAnnouncement = message; }
  }

  // For the customer, checked medicine IDs remain the only data sent to Flask.
  function customerBoxes() { return [...document.querySelectorAll('[data-pvc-medicine-checkbox]')]; }
  function selectedCustomerBoxes() { return customerBoxes().filter(input => input.checked); }
  function refreshCustomer() {
    if (!catalog || !customerBar) return;
    const selected = selectedCustomerBoxes();
    let total = 0;
    let units = 0;
    for (const box of customerBoxes()) {
      const card = box.closest('.pvc-selectable-card');
      card?.classList.toggle('pvc-is-selected', box.checked);
      const quantity = document.getElementById(`quantity-${box.value}`);
      if (box.checked) {
        const amount = Math.max(1, Number.parseInt(quantity?.value || '1', 10) || 1);
        total += Number.parseFloat(box.dataset.price || '0') * amount;
        units += amount;
      }
    }
    const count = document.getElementById('pvc-selected-count');
    const sub = document.getElementById('pvc-selected-subtotal');
    const submit = document.getElementById('pvc-floating-cart-submit');
    const clear = document.getElementById('pvc-clear-selection');
    if (count) count.textContent = `${selected.length} medicine${selected.length === 1 ? '' : 's'} selected · ${units} unit${units === 1 ? '' : 's'}`;
    if (sub) sub.textContent = `Estimated subtotal: ₱${money.format(total)}`;
    if (submit) submit.disabled = selected.length === 0 || selected.length > 30;
    if (clear) clear.disabled = selected.length === 0;
    customerBar.classList.toggle('pvc-has-selection', selected.length > 0);
  }
  if (catalog && customerBar) {
    document.body.classList.add('pvc-catalog-ready', 'pvc-has-floating-action');
    refreshCustomer();
    catalog.addEventListener('change', event => {
      const input = event.target;
      if (!(input instanceof HTMLElement)) return;
      if (input.matches('[data-pvc-medicine-checkbox]')) {
        if (input.checked && selectedCustomerBoxes().length > 30) {
          input.checked = false;
          announce('You can select at most 30 different medicines.');
        } else if (input.checked) {
          announce(`${input.dataset.medicineName || 'Medicine'} selected.`);
        }
      }
      if (input.matches('[data-pvc-quantity]')) {
        // Choosing more than one automatically selects that medicine.
        const id = input.id.replace('quantity-', '');
        const box = document.getElementById(`select-${id}`);
        if (box && !box.checked && Number.parseInt(input.value, 10) > 1) {
          if (selectedCustomerBoxes().length < 30) box.checked = true;
          else announce('Maximum 30 different medicines per cart.');
        }
      }
      refreshCustomer();
    });
    document.getElementById('pvc-clear-selection')?.addEventListener('click', () => {
      customerBoxes().forEach(box => { box.checked = false; });
      refreshCustomer();
      announce('Medicine selection cleared.');
    });
    catalog.addEventListener('submit', event => {
      if (selectedCustomerBoxes().length === 0) {
        event.preventDefault();
        announce('Please select at least one medicine.');
        return;
      }
      const button = document.getElementById('pvc-floating-cart-submit');
      if (button) { button.disabled = true; button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> Adding…'; }
    });
  }

  // Admin bulk restock: selections survive normal interaction and the existing
  // admin live-refresh skips polling while checkboxes are selected.
  function adminBoxes() { return [...document.querySelectorAll('[data-restock-select]')]; }
  function selectedAdminBoxes() { return adminBoxes().filter(box => box.checked); }
  function refreshAdmin() {
    if (!inventoryRegion || !adminBar) return;
    const boxes = adminBoxes();
    const selected = selectedAdminBoxes();
    adminBar.classList.toggle('pvc-is-visible', selected.length > 0);
    const label = document.getElementById('pvc-admin-selected-count');
    const confirm = document.getElementById('pvc-admin-review-restock');
    const lowCount = document.getElementById('pvc-admin-low-stock-count');
    if (label) label.textContent = `${selected.length} medicine${selected.length === 1 ? '' : 's'} selected`;
    if (confirm) confirm.disabled = selected.length === 0;
    if (lowCount) lowCount.textContent = String(boxes.filter(box => Number(box.dataset.stock) <= 10).length);
    // Keep the existing admin bulk-restock form controls synchronized.
    const existingCount = document.getElementById('restock-count');
    const existingButton = document.getElementById('restock-review');
    const selectAll = document.getElementById('restock-select-all');
    if (existingCount) existingCount.textContent = `${selected.length} selected`;
    if (existingButton) existingButton.disabled = selected.length === 0;
    if (selectAll) {
      selectAll.checked = boxes.length > 0 && selected.length === boxes.length;
      selectAll.indeterminate = selected.length > 0 && selected.length < boxes.length;
    }
    boxes.forEach(box => box.closest('tr')?.classList.toggle('pvc-admin-row-selected', box.checked));
  }
  if (inventoryRegion && adminBar) {
    document.body.classList.add('pvc-admin-enhanced');
    document.addEventListener('change', event => {
      if (event.target?.matches('[data-restock-select], #restock-select-all')) refreshAdmin();
    });
    document.addEventListener('click', event => {
      const low = event.target.closest?.('[data-pvc-select-low]');
      const clear = event.target.closest?.('[data-pvc-clear-restock]');
      if (low) {
        for (const box of adminBoxes()) box.checked = Number(box.dataset.stock) <= 10;
        refreshAdmin();
        announce('Low and out-of-stock medicines selected from the visible list.');
      }
      if (clear) {
        for (const box of adminBoxes()) box.checked = false;
        refreshAdmin();
        announce('Restock selection cleared.');
      }
    });
    // The original admin live-update replaces only inventoryRegion contents.
    // Refresh our counters when its table is swapped out.
    new MutationObserver(refreshAdmin).observe(inventoryRegion, {childList: true});
    refreshAdmin();
  }

  // Friendly shortcuts: '/' focuses page search unless already typing.
  document.addEventListener('keydown', event => {
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target;
    if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable="true"]')) return;
    const search = document.getElementById('search');
    if (search && search instanceof HTMLInputElement) {
      event.preventDefault(); search.focus(); search.select();
    }
  });

  // Back-to-top is available to customers and admins on long pages.
  const backToTop = document.createElement('button');
  backToTop.type = 'button';
  backToTop.className = 'pvc-back-to-top';
  backToTop.innerHTML = '<i class="bi bi-arrow-up" aria-hidden="true"></i><span class="visually-hidden">Back to top</span>';
  backToTop.setAttribute('aria-label', 'Back to top');
  backToTop.title = 'Back to top';
  document.body.appendChild(backToTop);
  let scrollScheduled = false;
  function setScrollState() {
    backToTop.classList.toggle('pvc-show-back-top', window.scrollY > 520);
    scrollScheduled = false;
  }
  window.addEventListener('scroll', () => {
    if (!scrollScheduled) { scrollScheduled = true; window.requestAnimationFrame(setScrollState); }
  }, {passive: true});
  backToTop.addEventListener('click', () => window.scrollTo({top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'}));
  setScrollState();
})();
