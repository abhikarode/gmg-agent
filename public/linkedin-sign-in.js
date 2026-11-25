async function openLinkedIn() {
  const status = document.querySelector("#sign-in-status");
  const options = {
    cache: "no-store",
    credentials: "same-origin",
    redirect: "error",
    signal: AbortSignal.timeout(15_000),
  };

  try {
    const csrf = await fetch("/api/auth/csrf", options);
    if (!csrf.ok) throw new Error("Could not start a sign-in session");
    const { csrfToken } = await csrf.json();
    if (typeof csrfToken !== "string" || !csrfToken) throw new Error("Missing sign-in token");

    const response = await fetch("/api/auth/signin/linkedin", {
      ...options,
      method: "POST",
      body: new URLSearchParams({ csrfToken, callbackUrl: "/", json: "true" }),
    });
    if (!response.ok) throw new Error("LinkedIn sign-in is unavailable");
    const redirect = new URL((await response.json()).url);
    if (redirect.origin !== "https://www.linkedin.com" || redirect.pathname !== "/oauth/v2/authorization") {
      throw new Error("Unexpected LinkedIn sign-in destination");
    }
    window.location.replace(redirect.href);
  } catch {
    status.textContent = "LinkedIn couldn’t open. Return to GMG sign-in to try again.";
  }
}

void openLinkedIn();
