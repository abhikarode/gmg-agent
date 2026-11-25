const requestMask = document.querySelector("#request-mask");
const requestLabel = document.querySelector("#request-label");
const requestRecovery = requestMask.querySelector(".request-recovery");
const requestStatus = document.querySelector("#request-status");
let pendingRequest;
let forwardingForm;
let revealTimer;
let recoveryTimer;

function showRequestMask() {
    if (typeof requestMask.showModal === "function") {
        requestMask.showModal();
    } else {
        requestMask.classList.add("request-mask-fallback");
        requestMask.setAttribute("open", "");
    }
}

function startRequest(owner) {
    pendingRequest = owner;
    owner.setAttribute("aria-busy", "true");
    requestLabel.textContent = owner.dataset.pending;
    recoveryTimer = window.setTimeout(() => { requestRecovery.hidden = false; }, 12_000);
}

for (const form of document.querySelectorAll("form[data-pending]")) {
    form.addEventListener("submit", event => {
        if (event.defaultPrevented || forwardingForm === form) return;
        event.preventDefault();
        if (pendingRequest) return;

        startRequest(form);
        form.inert = true;
        showRequestMask();

        const submitter = event.submitter ?? undefined;
        let sent = false;
        const send = () => {
            if (sent || pendingRequest !== form) return;
            sent = true;
            window.clearTimeout(sendTimer);
            forwardingForm = form;
            try {
                if (typeof form.requestSubmit === "function") form.requestSubmit(submitter);
                else form.submit();
            } finally {
                forwardingForm = undefined;
            }
        };
        // Give the browser a frame to paint before native navigation starts.
        const sendTimer = window.setTimeout(send, 100);
        window.requestAnimationFrame(() => window.requestAnimationFrame(send));
    });
}

for (const link of document.querySelectorAll("a[data-pending]")) {
    link.addEventListener("click", event => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey
            || event.shiftKey || event.altKey) return;
        if (pendingRequest) {
            event.preventDefault();
            return;
        }
        startRequest(link);
        revealTimer = window.setTimeout(showRequestMask, 220);
    });
}

requestMask.addEventListener("close", () => {
    if (pendingRequest) requestStatus.textContent = pendingRequest.dataset.pending;
});

window.addEventListener("pageshow", event => {
    if (!event.persisted || !pendingRequest) return;
    window.clearTimeout(revealTimer);
    window.clearTimeout(recoveryTimer);
    pendingRequest.removeAttribute("aria-busy");
    if (pendingRequest instanceof HTMLFormElement) pendingRequest.inert = false;
    pendingRequest = undefined;
    requestStatus.textContent = "";
    requestRecovery.hidden = true;
    if (typeof requestMask.close === "function" && requestMask.open) requestMask.close();
    else requestMask.removeAttribute("open");
});

const peopleSearch = document.querySelector("#people-search");
if (peopleSearch) {
    const examples = peopleSearch.parentElement.querySelector(".examples");
    const need = peopleSearch.elements.need;
    const place = peopleSearch.elements.place;
    for (const example of examples.querySelectorAll("button[data-need]")) {
        example.addEventListener("click", () => {
            if (peopleSearch.getAttribute("aria-busy") === "true") return;
            need.value = example.dataset.need;
            place.value = example.dataset.place || "";
            need.focus();
        });
    }
    examples.hidden = false;
}

const expertise = document.querySelector("form[data-expertise-limit]");
if (expertise) {
    const filter = expertise.querySelector("#topic-filter");
    const groups = [...expertise.querySelectorAll("details")];
    const choices = [...expertise.querySelectorAll("input[name=topics]")];
    const selection = expertise.querySelector("[data-selection]");
    const limit = Number(expertise.dataset.expertiseLimit);
    const updateSelection = () => {
        const selected = choices.filter(choice => choice.checked).length;
        selection.textContent = `${selected} of ${limit} selected`;
        for (const choice of choices) choice.disabled = !choice.checked && selected >= limit;
    };
    expertise.addEventListener("change", updateSelection);
    updateSelection();
    filter.addEventListener("input", () => {
        const query = filter.value.trim().toLocaleLowerCase();
        for (const group of groups) {
            const topics = [...group.querySelectorAll("label.topic")];
            for (const topic of topics) topic.hidden = !topic.textContent.toLocaleLowerCase().includes(query);
            group.hidden = topics.every(topic => topic.hidden);
            if (query && !group.hidden) group.open = true;
        }
    });
}
