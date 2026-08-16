// Vault add-key form: show only the extra fields the selected service needs,
// and relabel the secret field (API key vs. personal access token).
document.addEventListener("DOMContentLoaded", function () {
  var select = document.getElementById("service");
  var extraFields = document.querySelectorAll(".extra-field");
  var secretLabel = document.getElementById("secret-label");
  var labels = window.MITRA_SECRET_LABELS || {};

  function sync() {
    if (!select) return;
    var current = select.value;

    extraFields.forEach(function (field) {
      var forService = field.getAttribute("data-extra-for");
      var isActive = forService === current;
      field.hidden = !isActive;

      var input = field.querySelector("input");
      if (input) {
        var isRequired = input.hasAttribute("data-required-for");
        input.required = isActive && isRequired;
        if (!isActive) input.value = input.value; // leave value; server ignores unused fields
      }
    });

    if (secretLabel && labels[current]) {
      secretLabel.textContent = labels[current];
    }
  }

  if (select) {
    select.addEventListener("change", sync);
    sync();
  }

  // Confirm before any destructive form submit (e.g. "Remove" a connected service).
  document.addEventListener("submit", function (event) {
    var form = event.target;
    var message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });
});
