/* Pharmacityville admin updates: lightweight, same-origin polling.
 * Refresh only the visible data region, never the entire page.
 * No WebSockets, database migration, or external services needed.
 */
(() => {
  "use strict";
  const stateUrl = document.body.dataset.adminLiveUrl;
  if (!stateUrl) return;

  const INTERVAL_MS = 30000; // 30s: friendly to PythonAnywhere free-plan CPU quota.
  const region = document.querySelector("[data-admin-live-region]");
  const status = document.getElementById("admin-live-status-text");
  const statusContainer = status?.closest(".admin-live-status");
  const notice = document.getElementById("admin-live-toast");
  const noticeText = document.getElementById("admin-live-toast-text");
  const noticeDismiss = document.getElementById("admin-live-dismiss");

  let previous = null;
  let running = false;
  let timer = null;
  let noticeDismissedFor = 0;

  function updateStatus(message, offline = false) {
    if (status) status.textContent = message;
    statusContainer?.classList.toggle("is-offline", offline);
  }

  function updatePending(count) {
    document.querySelectorAll("[data-live-pending-count]").forEach((badge) => {
      badge.textContent = String(count);
      badge.classList.toggle("d-none", count === 0);
    });
  }

  function showNewOrder(orderId) {
    if (!notice || !noticeText || orderId <= noticeDismissedFor) return;
    noticeText.textContent = `New order received (latest: #${orderId}).`;
    notice.classList.remove("d-none");
  }

  noticeDismiss?.addEventListener("click", () => {
    noticeDismissedFor = Math.max(noticeDismissedFor, previous?.latest_order_id || 0);
    notice?.classList.add("d-none");
  });

  function hasOpenDialog() {
    return !!document.querySelector(".modal.show, .offcanvas.show");
  }

  async function refreshRegion() {
    if (!region || hasOpenDialog()) return;
    const response = await fetch(window.location.href, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Requested-With": "XMLHttpRequest" }
    });
    if (response.redirected && new URL(response.url).pathname.startsWith("/login")) {
      window.location.assign(response.url);
      return;
    }
    if (!response.ok) throw new Error(`Page refresh failed (${response.status})`);
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    const fresh = doc.querySelector("[data-admin-live-region]");
    if (!fresh || fresh.dataset.adminLiveRegion !== region.dataset.adminLiveRegion) {
      throw new Error("The live section was not found in the response");
    }
    // Keep search boxes, filter controls, sidebar, flash messages, etc. unchanged.
    region.replaceChildren(...Array.from(fresh.childNodes).map((node) => document.importNode(node, true)));
  }

  async function tick() {
    // Preserve bulk-restock selections until the admin submits or clears them.
    if (running || document.hidden || hasOpenDialog() || document.querySelector('[data-restock-select]:checked')) return;
    running = true;
    try {
      const response = await fetch(stateUrl, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Accept": "application/json" }
      });
      if (response.redirected && new URL(response.url).pathname.startsWith("/login")) {
        window.location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error(`Order check failed (${response.status})`);
      const current = await response.json();
      updatePending(current.pending_orders);
      if (previous && current.latest_order_id > previous.latest_order_id) {
        showNewOrder(current.latest_order_id);
      }
      const section = region?.dataset.adminLiveRegion;
      const field = ({dashboard: "dashboard_version", orders: "orders_version",
                      medicines: "medicines_version"})[section];
      // On first check, sync the UI in case something changed since page load.
      if (field && (!previous || current[field] !== previous[field])) {
        await refreshRegion();
      }
      previous = current;
      const now = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
      updateStatus(`Automatic updates on · Checked ${now} · Every 30 seconds`);
    } catch (error) {
      console.warn("Pharmacityville admin live update:", error);
      updateStatus("Connection interrupted. Will retry automatically.", true);
    } finally {
      running = false;
    }
  }

  // Poll on a timer, and promptly catch up when the admin returns to the tab.
  timer = window.setInterval(tick, INTERVAL_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) tick();
  });
  tick();
})();
