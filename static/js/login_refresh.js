/* Login-page conveniences only. Credentials are sent by the existing HTTPS POST. */
(function () {
  'use strict';
  function initialize() {
    var form = document.getElementById('pvc-login-form');
    if (!form || form.dataset.pvcInitialized === 'true') return;
    form.dataset.pvcInitialized = 'true';

    var email = document.getElementById('email');
    var password = document.getElementById('password');
    var toggle = document.getElementById('pvc-password-toggle');
    var caps = document.getElementById('pvc-caps-warning');
    var remember = document.getElementById('pvc-remember-email');
    var submit = document.getElementById('pvc-login-submit');
    var submitLabel = submit ? submit.querySelector('.pvc-login-submit-label') : null;
    var spinner = submit ? submit.querySelector('.pvc-login-spinner') : null;
    var status = document.getElementById('pvc-login-status');
    var storageKey = 'pvc-remembered-email';

    // Only save the email address when the visitor explicitly opts in.
    try {
      var saved = localStorage.getItem(storageKey);
      if (saved && email && !email.value) email.value = saved;
      if (saved && remember) remember.checked = true;
    } catch (e) { /* Browsers can disable storage. Login still works. */ }

    if (toggle && password) {
      toggle.addEventListener('click', function () {
        var show = password.type === 'password';
        password.type = show ? 'text' : 'password';
        toggle.setAttribute('aria-pressed', String(show));
        toggle.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
        toggle.setAttribute('title', show ? 'Hide password' : 'Show password');
        var icon = toggle.querySelector('.bi');
        if (icon) icon.className = show ? 'bi bi-eye-slash' : 'bi bi-eye';
        var srText = toggle.querySelector('.visually-hidden');
        if (srText) srText.textContent = show ? 'Hide password' : 'Show password';
        password.focus({ preventScroll: true });
      });
      function updateCaps(event) {
        if (caps && event.getModifierState) caps.hidden = !event.getModifierState('CapsLock');
      }
      password.addEventListener('keydown', updateCaps);
      password.addEventListener('keyup', updateCaps);
      password.addEventListener('blur', function () { if (caps) caps.hidden = true; });
    }

    function trimEmail() { if (email) email.value = email.value.trim(); }
    if (email) email.addEventListener('blur', trimEmail);

    form.addEventListener('submit', function (event) {
      trimEmail();
      if (!form.checkValidity()) return; // Preserve native validation messages.
      try {
        if (remember && remember.checked && email) localStorage.setItem(storageKey, email.value);
        else localStorage.removeItem(storageKey);
      } catch (e) { /* Do not block login if browser storage is unavailable. */ }

      // Do not touch the password, CSRF token, or actual backend authentication.
      if (submit && submit.disabled) { event.preventDefault(); return; }
      if (submit) submit.disabled = true;
      if (submitLabel) submitLabel.textContent = 'Signing in…';
      if (spinner) spinner.hidden = false;
      if (status) status.textContent = 'Signing in, please wait.';
    });

    // Browsers may restore a previously submitted page via back/forward cache.
    window.addEventListener('pageshow', function () {
      if (submit) submit.disabled = false;
      if (submitLabel) submitLabel.textContent = 'Sign in';
      if (spinner) spinner.hidden = true;
      if (status) status.textContent = '';
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
}());