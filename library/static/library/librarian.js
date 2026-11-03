// The reader's own Gemini key: kept by this browser only, sent straight to Google, never to Neuralib.
(function () {
  "use strict";
  var STORE_KEY = "neuralib-gemini-key";
  var GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/";

  function storedKey() {
    try { return sessionStorage.getItem(STORE_KEY) || localStorage.getItem(STORE_KEY) || ""; } catch (e) { return ""; }
  }

  // ---- The AI key page ----
  var keyForm = document.getElementById("ai-key-form");
  if (keyForm) {
    var input = document.getElementById("gemini-key");
    var remember = document.getElementById("remember-key");
    var keyStatus = document.getElementById("ai-key-status");
    var showStatus = function () {
      var where = "";
      try { where = localStorage.getItem(STORE_KEY) ? "on this device" : (sessionStorage.getItem(STORE_KEY) ? "until you close this tab" : ""); } catch (e) {}
      keyStatus.textContent = where ? "A key is saved " + where + "." : "No key saved in this browser.";
    };
    keyForm.addEventListener("submit", function (event) {
      event.preventDefault();
      var value = input.value.trim();
      if (!value) { return; }
      try {
        localStorage.removeItem(STORE_KEY);
        sessionStorage.removeItem(STORE_KEY);
        (remember.checked ? localStorage : sessionStorage).setItem(STORE_KEY, value);
      } catch (e) {
        keyStatus.textContent = "This browser does not let the page store the key.";
        return;
      }
      input.value = "";
      showStatus();
    });
    document.getElementById("forget-key").addEventListener("click", function () {
      try { localStorage.removeItem(STORE_KEY); sessionStorage.removeItem(STORE_KEY); } catch (e) {}
      showStatus();
    });
    showStatus();
  }

  // ---- The librarian page ----
  var form = document.getElementById("librarian-form");
  if (!form) { return; }
  var key = storedKey();
  var statusLine = document.getElementById("librarian-status");
  var results = document.getElementById("librarian-results");

  if (!key) {
    if (form.dataset.siteKey !== "true") {
      document.getElementById("no-key").hidden = false;
      form.querySelector("button[type=submit]").disabled = true;
    }
    return;  // With the site's key the form posts normally.
  }
  document.getElementById("key-status").textContent = "Answers with your own Gemini key, from this browser.";

  function gemini(model, method, body) {
    return fetch(GEMINI + model + ":" + method, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify(body)
    }).then(function (response) {
      if (response.status === 429) { throw new Error("Your Gemini quota is used up for now. Try again later."); }
      if (!response.ok) { throw new Error("Gemini answered HTTP " + response.status + ". Check your key on the AI key page."); }
      return response.json();
    });
  }

  function textOf(answer) {
    var parts = (((answer.candidates || [])[0] || {}).content || {}).parts || [];
    return (parts[0] || {}).text || "";
  }

  function neuralib(url, data) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value },
      body: JSON.stringify(data)
    }).then(function (response) {
      return response.json().then(function (json) {
        if (!response.ok) { throw new Error(json.error || "Neuralib could not check the answer."); }
        return json;
      });
    });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var question = form.querySelector("[name=question]").value.trim();
    if (!question) { return; }
    var button = form.querySelector("button[type=submit]");
    button.disabled = true;
    results.textContent = "";
    statusLine.textContent = "Asking the librarian…";
    // 1. Neuralib writes the request, with the whole catalog and the closed list of ids.
    neuralib(form.dataset.requestUrl, { question: question }).then(function (pending) {
      // 2. The model picks, from Google with the reader's key.
      return gemini(pending.model, "generateContent", pending.body).then(textOf).then(function (text) {
        // 3. Neuralib checks the answer against the catalog and returns what passed.
        return neuralib(form.dataset.answerUrl, { token: pending.token, text: text });
      });
    }).then(function (checked) {
      statusLine.textContent = "";
      results.innerHTML = checked.html;  // Rendered by Django's templates, escaped there.
    }).catch(function (error) {
      statusLine.textContent = error.message;
    }).then(function () {
      button.disabled = false;
    });
  });
})();
