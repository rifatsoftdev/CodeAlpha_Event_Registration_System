const TOKEN_KEY = "gather_access_token";

const eventList = document.querySelector("#event-list");
const notice = document.querySelector("#notice");
const registerDialog = document.querySelector("#register-dialog");
const registerForm = document.querySelector("#register-form");
let selectedEvent = null;
let currentUser = null;
let allEvents = [];

function token() {
  return localStorage.getItem(TOKEN_KEY);
}

function authHeaders() {
  return token() ? { Authorization: `Bearer ${token()}` } : {};
}

async function request(path, options = {}) {
  const headers = { ...authHeaders(), ...options.headers };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : message;
    } catch {
      // Keep the HTTP status message when the server does not return JSON.
    }
    if (response.status === 401 && token()) {
      localStorage.removeItem(TOKEN_KEY);
      currentUser = null;
      updateAccountUI();
    }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function eventDate(value, options) {
  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "Date to be announced" : new Intl.DateTimeFormat(undefined, options).format(date);
}

function setNotice(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle("error", isError);
  notice.hidden = !message;
  if (message) {
    document.querySelector("#events").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function updateAccountUI() {
  const label = document.querySelector("#user-label");
  const dashboardLink = document.querySelector("#dashboard-link");
  const signInLink = document.querySelector("#auth-button");
  const signoutButton = document.querySelector("#signout-button");
  label.textContent = currentUser ? `Hi, ${currentUser.username}` : "";
  label.hidden = !currentUser;
  dashboardLink.hidden = !currentUser;
  signInLink.hidden = Boolean(currentUser);
  signoutButton.hidden = !currentUser;
}

async function loadAccount() {
  if (!token()) {
    updateAccountUI();
    return;
  }
  try {
    currentUser = await request("/auth/me");
  } catch {
    currentUser = null;
  }
  updateAccountUI();
}

function renderEvents(events) {
  const count = document.querySelector("#event-count");
  if (count) count.textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;
  if (!events.length) {
    eventList.innerHTML = '<p class="empty-state">No matching events right now. Try a different search or check back soon.</p>';
    return;
  }
  eventList.innerHTML = events.map((event) => {
    const full = event.spots_left <= 0;
    const date = eventDate(event.start_time, { month: "short", day: "numeric", year: "numeric" });
    const time = eventDate(event.start_time, { hour: "numeric", minute: "2-digit" });
    return `
      <article class="event-card">
        <div class="event-card-top">
          <span class="event-date">${escapeHTML(date)}</span>
          <span class="spots${full ? " full" : ""}">${full ? "All spots filled" : `${event.spots_left} spot${event.spots_left === 1 ? "" : "s"} left`}</span>
        </div>
        <h3>${escapeHTML(event.title)}</h3>
        <p class="event-description">${escapeHTML(event.description || "A chance to get together and try something new.")}</p>
        <div class="event-meta"><span>${escapeHTML(event.location)}</span><span>${escapeHTML(time)}</span></div>
        <div class="event-card-bottom">
          <span class="event-organizer">Hosted by the community</span>
          <button class="register-button" type="button" data-event-id="${event.id}" ${full ? "disabled" : ""}>${full ? "Full" : "Save a spot ↗"}</button>
        </div>
      </article>`;
  }).join("");
}

async function loadEvents() {
  try {
    allEvents = await request("/events?upcoming=true&limit=100");
    filterEvents();
  } catch (error) {
    eventList.innerHTML = `<p class="empty-state">We couldn't load events. ${escapeHTML(error.message)} Please refresh to try again.</p>`;
  }
}

function filterEvents() {
  const query = document.querySelector("#event-search").value.trim().toLocaleLowerCase();
  const filtered = allEvents.filter((event) =>
    [event.title, event.description, event.location].some((value) => String(value || "").toLocaleLowerCase().includes(query))
  );
  renderEvents(filtered);
}

document.querySelector("#event-search").addEventListener("input", filterEvents);

eventList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-event-id]");
  if (!button) return;
  if (!token()) {
    window.location.href = "/login?next=%2F";
    return;
  }
  selectedEvent = button.dataset.eventId;
  document.querySelector("#register-title").textContent = button.closest(".event-card").querySelector("h3").textContent;
  document.querySelector("#register-error").hidden = true;
  registerDialog.showModal();
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(registerForm);
  const error = document.querySelector("#register-error");
  const submit = registerForm.querySelector('[type="submit"]');
  submit.disabled = true;
  error.hidden = true;
  try {
    await request(`/events/${selectedEvent}/register`, {
      method: "POST",
      body: JSON.stringify({
        full_name: form.get("full_name"),
        phone: form.get("phone"),
        notes: form.get("notes"),
      }),
    });
    registerDialog.close();
    registerForm.reset();
    setNotice("You're registered! We'll see you there.");
    await loadEvents();
  } catch (requestError) {
    error.textContent = requestError.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#signout-button").addEventListener("click", () => {
  localStorage.removeItem(TOKEN_KEY);
  currentUser = null;
  updateAccountUI();
});

document.querySelectorAll("[data-close]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog").close());
});
document.querySelectorAll(".dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});

loadAccount();
loadEvents();
