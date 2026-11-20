const TOKEN_KEY = "gather_access_token";
const form = document.querySelector("#login-form, #signup-form, #forgot-form, #reset-form");
const errorMessage = document.querySelector("#form-error");
const successMessage = document.querySelector("#form-success");

function errorText(body, status) {
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((error) => error.msg).join(". ");
  return `Request failed (${status})`;
}

async function send(path, options) {
  const response = await fetch(path, options);
  let body = {};
  try { body = await response.json(); } catch { /* Keep a status-based error below. */ }
  if (!response.ok) throw new Error(errorText(body, response.status));
  return body;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  errorMessage.hidden = true;
  if (successMessage) successMessage.hidden = true;
  try {
    if (form.id === "signup-form") {
      await send("/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: data.get("username"), email: data.get("email"), password: data.get("password") }),
      });
      const credentials = new URLSearchParams({ username: data.get("username"), password: data.get("password") });
      const token = await send("/auth/login", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: credentials });
      localStorage.setItem(TOKEN_KEY, token.access_token);
      window.location.href = "/dashboard";
      return;
    }

    if (form.id === "login-form") {
      const credentials = new URLSearchParams({ username: data.get("username"), password: data.get("password") });
      const token = await send("/auth/login", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: credentials });
      localStorage.setItem(TOKEN_KEY, token.access_token);
      const next = new URLSearchParams(window.location.search).get("next");
      window.location.href = next?.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
      return;
    }

    if (form.id === "forgot-form") {
      const result = await send("/auth/password-reset/request", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.get("email") }),
      });
      successMessage.textContent = result.message;
      successMessage.hidden = false;
      form.reset();
      return;
    }

    const password = data.get("new_password");
    if (password !== data.get("confirm_password")) throw new Error("The passwords do not match.");
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) throw new Error("This reset link is missing or invalid. Request a new one.");
    const result = await send("/auth/password-reset/confirm", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: password }),
    });
    successMessage.textContent = result.message;
    successMessage.hidden = false;
    form.reset();
    submit.hidden = true;
  } catch (error) {
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
  } finally {
    submit.disabled = false;
  }
});
