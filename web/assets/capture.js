/* Sign-up forms: bot trap, Google reCAPTCHA “I’m not a robot” checkbox, and the emailed 6-digit code step.
   Usage: DotxCapture.attach(formElement, { payload, fail, busy, hide, done }) */
(function () {
  'use strict';
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var configPromise = null, recaptchaPromise = null;

  function getConfig() {
    if (!configPromise) {
      configPromise = fetch('/api/config').then(function (r) { return r.json(); })
        .catch(function () { return {}; });
    }
    return configPromise;
  }

  // Loads Google's script once; resolves with grecaptcha (or null if the browser blocked it).
  function loadRecaptcha() {
    if (!recaptchaPromise) {
      recaptchaPromise = new Promise(function (resolve) {
        var s = document.createElement('script');
        s.src = 'https://www.google.com/recaptcha/api.js?render=explicit';
        s.async = true;
        s.onload = function () {
          if (!window.grecaptcha) { resolve(null); return; }
          window.grecaptcha.ready(function () { resolve(window.grecaptcha); });
        };
        s.onerror = function () { resolve(null); };
        document.head.appendChild(s);
      });
    }
    return recaptchaPromise;
  }

  function addStyles() {
    if (document.getElementById('dotx-capture-css')) return;
    var css = document.createElement('style');
    css.id = 'dotx-capture-css';
    css.textContent =
      '.dx-trap{position:absolute!important;left:-9999px!important;width:1px;height:1px;overflow:hidden}' +
      '.dx-captcha{flex-basis:100%;grid-column:1/-1;margin:4px 0;max-width:100%;overflow:hidden}' +
      '.dx-verify{flex-basis:100%;grid-column:1/-1;text-align:left}' +
      '.dx-verify p{margin:0 0 12px}' +
      '.dx-verify .dx-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}' +
      '.dx-verify input{flex:0 1 200px;min-width:0;padding:.8rem 1rem;border-radius:10px;border:1px solid rgba(173,197,228,.3);' +
        'background:rgba(255,255,255,.05);color:inherit;font:inherit;font-size:1.3rem;letter-spacing:.3em;text-align:center}' +
      '.dx-verify input:focus{outline:2px solid #e8c06a;outline-offset:1px}' +
      '.dx-verify .dx-links{margin-top:12px;font-size:.86rem;opacity:.85}' +
      '.dx-verify .dx-links button{background:none;border:none;padding:0;color:#e8c06a;font:inherit;cursor:pointer;text-decoration:underline}' +
      '.dx-verify .dx-err{color:#e39b9b;margin:10px 0 0;min-height:1.2em}' +
      '.dx-verify .dx-note{color:#8fe3bf;margin:10px 0 0}';
    document.head.appendChild(css);
  }

  function post(url, data) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
      .then(function (r) { return r.json().catch(function () { return { ok: r.ok }; }); });
  }

  function attach(form, opts) {
    if (!form) return;
    addStyles();
    var fail = opts.fail || function () {};
    var busy = opts.busy || function () {};
    var submitBtn = form.querySelector('button[type=submit],button:not([type])');

    // Bot trap: a field people never see. Scripts that fill every field give themselves away.
    var trap = document.createElement('div');
    trap.className = 'dx-trap';
    trap.setAttribute('aria-hidden', 'true');
    trap.innerHTML = '<label>Leave this field empty<input type="text" name="website" tabindex="-1" autocomplete="off"></label>';
    form.appendChild(trap);

    // The "I'm not a robot" checkbox (shown only when the site has reCAPTCHA keys).
    var captchaOn = false, g = null, widgetId = null;
    var captchaBox = document.createElement('div');
    captchaBox.className = 'dx-captcha';
    var anchor = opts.captchaBefore || (submitBtn && submitBtn.parentNode !== form ? submitBtn.parentNode : submitBtn);
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(captchaBox, anchor); else form.appendChild(captchaBox);
    getConfig().then(function (cfg) {
      if (!cfg || !cfg.recaptchaSiteKey) return;
      captchaOn = true;
      loadRecaptcha().then(function (lib) {
        if (!lib) return;
        g = lib;
        widgetId = g.render(captchaBox, { sitekey: cfg.recaptchaSiteKey, theme: 'dark' });
      });
    });
    function captchaAnswer() { return g && widgetId !== null ? g.getResponse(widgetId) : ''; }
    function captchaReset() { if (g && widgetId !== null) g.reset(widgetId); }

    var panel = null, token = null, sentTo = '';

    function showVerify() {
      captchaBox.style.display = 'none';
      (opts.hide ? opts.hide() : []).forEach(function (el) { el.setAttribute('data-dx-hidden', el.style.display || ''); el.style.display = 'none'; });
      if (!panel) {
        panel = document.createElement('div');
        panel.className = 'dx-verify';
        panel.innerHTML =
          '<p class="dx-lead"></p>' +
          '<div class="dx-row"><input type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="9" ' +
          'aria-label="6-digit confirmation code" placeholder="000000">' +
          '<button type="button" class="btn btn-gold dx-go">Confirm</button></div>' +
          '<p class="dx-err" role="alert"></p>' +
          '<p class="dx-links"><button type="button" class="dx-again">Send a new code</button> &nbsp;·&nbsp; ' +
          '<button type="button" class="dx-back">Use a different email</button></p>';
        form.appendChild(panel);
        panel.querySelector('.dx-go').addEventListener('click', confirmCode);
        panel.querySelector('input').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); confirmCode(); } });
        panel.querySelector('.dx-again').addEventListener('click', resend);
        panel.querySelector('.dx-back').addEventListener('click', goBack);
      }
      panel.style.display = '';
      panel.querySelector('.dx-lead').textContent = 'We emailed a 6-digit code to ' + sentTo +
        '. Enter it here to confirm your email (check your spam folder if you don’t see it).';
      setErr('');
      var input = panel.querySelector('input'); input.value = ''; input.focus();
    }

    function setErr(text, good) {
      var el = panel.querySelector('.dx-err');
      el.textContent = text; el.className = good ? 'dx-note' : 'dx-err';
    }

    function goBack() {
      panel.style.display = 'none';
      form.querySelectorAll('[data-dx-hidden]').forEach(function (el) { el.style.display = el.getAttribute('data-dx-hidden'); el.removeAttribute('data-dx-hidden'); });
      captchaBox.style.display = ''; captchaReset(); busy(false); token = null;
    }

    function confirmCode() {
      var code = (panel.querySelector('input').value || '').replace(/\D/g, '');
      if (code.length !== 6) { setErr('Enter the 6-digit code from the email.'); return; }
      var go = panel.querySelector('.dx-go'); go.disabled = true; setErr('');
      post('/api/subscribe/verify', { token: token, code: code }).then(function (d) {
        go.disabled = false;
        if (d && d.ok) { panel.style.display = 'none'; opts.done && opts.done(d); }
        else setErr((d && d.error) || 'Something went wrong. Please try again.');
      }).catch(function () { go.disabled = false; setErr('Network error. Please try again.'); });
    }

    function resend() {
      setErr('');
      post('/api/subscribe/resend', { token: token }).then(function (d) {
        if (d && d.ok && d.token) { token = d.token; setErr('A new code is on its way.', true); }
        else setErr((d && d.error) || 'Please try again in a moment.');
      }).catch(function () { setErr('Network error. Please try again.'); });
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var data = opts.payload();
      if (!EMAIL_RE.test(data.email || '')) { fail('Please enter a valid email.'); return; }
      if (captchaOn && !g) {
        fail('The “I’m not a robot” check couldn’t load. Please switch off any ad or tracker blocker for this page and reload.');
        return;
      }
      if (captchaOn && g && !captchaAnswer()) { fail('Please tick the “I’m not a robot” box.'); return; }
      data.website = (form.querySelector('input[name=website]') || {}).value || '';
      data.captcha = captchaAnswer();
      busy(true); fail('');
      post('/api/subscribe', data).then(function (d) {
        if (d && d.ok && d.verify && d.token) { token = d.token; sentTo = data.email; showVerify(); }
        else if (d && d.ok) { opts.done && opts.done({ ok: true, intent: data.intent || '' }); }
        else { fail((d && d.error) || 'Something went wrong. Please try again.'); captchaReset(); busy(false); }
      }).catch(function () { fail('Network error. Please try again.'); captchaReset(); busy(false); });
    });
  }

  window.DotxCapture = { attach: attach };
})();
