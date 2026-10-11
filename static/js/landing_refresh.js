
document.addEventListener("DOMContentLoaded", function () {
  if (!document.querySelector(".home-shell")) return;
  const statusEl = document.querySelector("[data-store-status]");
  if (statusEl) {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Manila', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date());
    const value = (type) => parts.find((part) => part.type === type)?.value || '';
    const day = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].indexOf(value('weekday'));
    const minutes = Number(value('hour')) * 60 + Number(value('minute'));
    const weekdayOpen = 8 * 60;
    const weekdayClose = 19 * 60;
    const sundayOpen = 9 * 60;
    const sundayClose = 17 * 60;
    let isOpen = false;
    let message = "Today's schedule unavailable";
    if (day >= 1 && day <= 6) {
      isOpen = minutes >= weekdayOpen && minutes < weekdayClose;
      message = isOpen ? "Demo: Open • until 7:00 PM" : "Demo: Closed • sample opens 8:00 AM";
    } else {
      isOpen = minutes >= sundayOpen && minutes < sundayClose;
      message = isOpen ? "Demo: Open • until 5:00 PM" : "Demo: Closed • sample opens 9:00 AM";
    }
    statusEl.textContent = message;
    statusEl.classList.add(isOpen ? "open" : "closed");
  }

  const topBtn = document.querySelector("[data-back-to-top]");
  if (topBtn) {
    const updateButton = () => topBtn.classList.toggle("show", window.scrollY > 500);
    updateButton();
    window.addEventListener("scroll", updateButton, { passive: true });
    topBtn.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }
});