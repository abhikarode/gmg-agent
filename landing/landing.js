const signIn = document.querySelector("#sign-in");
const signInStatus = document.querySelector("#sign-in-status");
let opening = false;

signIn.addEventListener("click", (event) => {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  if (opening) {
    event.preventDefault();
    return;
  }
  opening = true;
  signIn.setAttribute("aria-disabled", "true");
  signInStatus.textContent = "The Community Desk is loading. Browse GMG news and events while it opens.";
});

window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  opening = false;
  signIn.removeAttribute("aria-disabled");
  signInStatus.textContent = "";
});

for (const event of document.querySelectorAll("[data-until]")) {
  event.hidden = Date.parse(event.dataset.until) <= Date.now();
}
