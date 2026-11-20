const TOKEN_KEY = "gather_access_token";
const dashboardMessage = document.querySelector("#dashboard-message");
let currentUser;
let registrations = [];
let ownEvents = [];
let editingEventId = null;

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function formatDate(value, options = { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }) {
  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, options).format(date);
}

function eventStatus(event) {
  const start = new Date(event.start_time.endsWith("Z") ? event.start_time : `${event.start_time}Z`).getTime();
  const end = new Date(event.end_time.endsWith("Z") ? event.end_time : `${event.end_time}Z`).getTime();
  const now = Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return "Status unavailable";
  if (now < start) return "Upcoming";
  if (now < end) return "In progress";
  return "Completed";
}

async function request(path, options = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = { ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) {
        message = body.detail.map((issue) => {
          const field = Array.isArray(issue.loc) ? issue.loc.slice(1).join(" → ") : "";
          return field ? `${field}: ${issue.msg}` : issue.msg;
        }).join(". ");
      }
    } catch {
      // Keep the HTTP status message for non-JSON responses.
    }
    if (response.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      window.location.replace("/login");
    }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function showMessage(message, isError = false) {
  dashboardMessage.textContent = message;
  dashboardMessage.classList.toggle("error", isError);
  dashboardMessage.hidden = !message;
}

function renderRegistrations() {
  const target = document.querySelector("#registrations-list");
  renderDashboardStats();
  if (!registrations.length) {
    target.innerHTML = '<p class="empty-state">You haven’t registered for an event yet. Find something that sounds fun and save your spot.</p>';
    return;
  }
  target.innerHTML = registrations.map((registration) => `
    <article class="dashboard-row">
      <div class="dashboard-row-date"><span>${escapeHTML(formatDate(registration.event_start_time, { month: "short" }))}</span><strong>${escapeHTML(formatDate(registration.event_start_time, { day: "2-digit" }))}</strong></div>
      <div class="dashboard-row-main"><h3>${escapeHTML(registration.event_title)}</h3><p>${escapeHTML(formatDate(registration.event_start_time))}</p></div>
      <span class="status-pill ${registration.status === "confirmed" ? "status-confirmed" : "status-cancelled"}">${escapeHTML(registration.status)}</span>
      ${registration.status === "confirmed" ? `<button class="row-action cancel-action" type="button" data-cancel-id="${registration.id}">Cancel</button>` : ""}
    </article>`).join("");
}

function renderOrganizerEvents() {
  const target = document.querySelector("#organizer-events");
  renderDashboardStats();
  if (!ownEvents.length) {
    target.innerHTML = '<p class="empty-state">You haven’t published an event yet. Create one to bring people together.</p>';
    return;
  }
  target.innerHTML = ownEvents.map((event) => `
    <article class="dashboard-row">
      <div class="dashboard-row-date"><span>${escapeHTML(formatDate(event.start_time, { month: "short" }))}</span><strong>${escapeHTML(formatDate(event.start_time, { day: "2-digit" }))}</strong></div>
      <div class="dashboard-row-main"><h3>${escapeHTML(event.title)}</h3><p>${escapeHTML(formatDate(event.start_time))} · ${escapeHTML(event.location)}</p></div>
      <span class="status-pill status-event">${escapeHTML(eventStatus(event))}</span>
      <span class="status-pill">${event.capacity - event.spots_left}/${event.capacity} spots</span>
      <button class="row-action attendees-action" type="button" data-attendees-id="${event.id}">Attendees</button>
      <button class="row-action edit-action" type="button" data-edit-id="${event.id}">Edit</button>
      <button class="row-action delete-action" type="button" data-delete-id="${event.id}">Delete</button>
    </article>`).join("");
}

function renderDashboardStats() {
  const confirmedRegistrations = registrations.filter((item) => item.status === "confirmed").length;
  const organizer = Boolean(currentUser?.is_organizer);
  document.querySelector("#stat-primary").textContent = organizer ? ownEvents.length : confirmedRegistrations;
  document.querySelector("#stat-primary-label").textContent = organizer ? "Events hosted" : "Confirmed spots";
  document.querySelector("#stat-secondary").textContent = organizer ? confirmedRegistrations : registrations.length - confirmedRegistrations;
  document.querySelector("#stat-secondary-label").textContent = organizer ? "My registrations" : "Cancelled";
}

function toLocalDateTime(value) {
  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 16);
}

function openEventForm(eventToEdit = null) {
  const form = document.querySelector("#event-form");
  const dialog = document.querySelector("#event-dialog");
  const formData = {
    title: document.querySelector("#event-title"),
    description: document.querySelector("#event-description"),
    location: document.querySelector("#event-location"),
    start_time: document.querySelector("#event-start"),
    end_time: document.querySelector("#event-end"),
    capacity: document.querySelector("#event-capacity"),
  };
  editingEventId = eventToEdit?.id ?? null;
  formData.start_time.removeAttribute("min");
  formData.end_time.removeAttribute("min");
  document.querySelector("#event-form-label").textContent = eventToEdit ? "UPDATE EVENT" : "BRING PEOPLE TOGETHER";
  document.querySelector("#event-form-title").textContent = eventToEdit ? "Update your event." : "Create an event.";
  document.querySelector("#event-form-submit").innerHTML = eventToEdit
    ? 'Save changes <span aria-hidden="true">→</span>'
    : 'Publish event <span aria-hidden="true">→</span>';
  if (eventToEdit) {
    formData.title.value = eventToEdit.title;
    formData.description.value = eventToEdit.description || "";
    formData.location.value = eventToEdit.location;
    formData.start_time.value = toLocalDateTime(eventToEdit.start_time);
    formData.end_time.value = toLocalDateTime(eventToEdit.end_time);
    formData.capacity.value = eventToEdit.capacity;
  } else {
    form.reset();
    const minimumStart = new Date();
    minimumStart.setSeconds(0, 0);
    minimumStart.setMinutes(minimumStart.getMinutes() + 1);
    const localMinimum = new Date(minimumStart.getTime() - minimumStart.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
    formData.start_time.min = localMinimum;
    formData.end_time.min = localMinimum;
  }
  document.querySelector("#event-error").hidden = true;
  dialog.showModal();
}

async function loadDashboard() {
  if (!localStorage.getItem(TOKEN_KEY)) {
    window.location.replace("/login?next=%2Fdashboard");
    return;
  }
  try {
    currentUser = await request("/auth/me");
    document.querySelector("#dashboard-username").textContent = currentUser.username;
    document.querySelector("#dashboard-subtitle").textContent = "Manage your events and registrations.";
    const [events, myRegistrations] = await Promise.all([
      currentUser.is_organizer ? request("/events?limit=100") : Promise.resolve([]),
      request("/registrations/me"),
    ]);
    ownEvents = events.filter((item) => item.organizer_id === currentUser.id);
    registrations = myRegistrations;
    document.querySelector("#organizer-section").hidden = !currentUser.is_organizer;
    renderOrganizerEvents();
    renderRegistrations();
  } catch (error) {
    showMessage(error.message, true);
  }
}

document.querySelector("#signout-button").addEventListener("click", () => {
  localStorage.removeItem(TOKEN_KEY);
  window.location.replace("/");
});

document.querySelector("#new-event-button").addEventListener("click", () => {
  openEventForm();
});

document.querySelector("#event-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const error = document.querySelector("#event-error");
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  error.hidden = true;
  try {
    const start = new Date(values.get("start_time"));
    const end = new Date(values.get("end_time"));
    if (!editingEventId && start <= new Date()) throw new Error("Choose a start time at least one minute in the future.");
    if (end <= start) throw new Error("End time must be after start time.");
    await request(editingEventId ? `/events/${editingEventId}` : "/events", {
      method: editingEventId ? "PATCH" : "POST",
      body: JSON.stringify({
        title: values.get("title"),
        description: values.get("description"),
        location: values.get("location"),
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        capacity: Number(values.get("capacity")),
      }),
    });
    form.reset();
    document.querySelector("#event-dialog").close();
    showMessage(editingEventId ? "Your event has been updated." : "Your event has been published.");
    editingEventId = null;
    await loadDashboard();
  } catch (requestError) {
    error.textContent = requestError.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#organizer-events").addEventListener("click", async (event) => {
  const attendeesButton = event.target.closest("[data-attendees-id]");
  const editButton = event.target.closest("[data-edit-id]");
  const deleteButton = event.target.closest("[data-delete-id]");
  if (editButton) {
    const eventToEdit = ownEvents.find((item) => item.id === Number(editButton.dataset.editId));
    if (eventToEdit) openEventForm(eventToEdit);
  }
  if (attendeesButton) {
    const panel = document.querySelector("#attendees-panel");
    panel.hidden = false;
    panel.innerHTML = '<p class="loading-message">Loading attendee list...</p>';
    try {
      const attendees = await request(`/events/${attendeesButton.dataset.attendeesId}/registrations`);
      panel.innerHTML = `<div class="dashboard-section-heading"><h3>Event attendees</h3><button class="row-action" type="button" data-hide-attendees>Close</button></div>${
        attendees.length ? attendees.map((attendee) => `<div class="attendee-row"><strong>${escapeHTML(attendee.full_name)}</strong><span>${escapeHTML(attendee.event_title)}</span><span>${escapeHTML(attendee.phone || "No phone")}</span><span>${escapeHTML(attendee.status)}</span></div>`).join("") : '<p class="empty-state">No registrations for this event yet.</p>'
      }`;
    } catch (error) {
      panel.innerHTML = `<p class="empty-state">${escapeHTML(error.message)}</p>`;
    }
  }
  if (deleteButton && window.confirm("Delete this event? This cannot be undone.")) {
    deleteButton.disabled = true;
    try {
      await request(`/events/${deleteButton.dataset.deleteId}`, { method: "DELETE" });
      showMessage("Event deleted.");
      await loadDashboard();
    } catch (error) {
      deleteButton.disabled = false;
      showMessage(error.message, true);
    }
  }
});

document.querySelector("#attendees-panel").addEventListener("click", (event) => {
  if (event.target.closest("[data-hide-attendees]")) {
    const panel = document.querySelector("#attendees-panel");
    panel.hidden = true;
    panel.innerHTML = "";
  }
});

document.querySelector("#registrations-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-cancel-id]");
  if (!button) return;
  button.disabled = true;
  try {
    await request(`/registrations/${button.dataset.cancelId}`, { method: "DELETE" });
    registrations = await request("/registrations/me");
    renderRegistrations();
    showMessage("Your registration was cancelled.");
  } catch (error) {
    button.disabled = false;
    showMessage(error.message, true);
  }
});

document.querySelectorAll("[data-close]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog").close());
});

loadDashboard();
