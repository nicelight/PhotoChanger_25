(function () {
  const form = document.getElementById("login-form");
  const errorBox = document.getElementById("login-error");
  const toggleBtn = document.getElementById("toggle-password");
  const passwordInput = document.getElementById("password");
  const submitBtn = document.getElementById("login-submit");

  function setMessage(text, kind = "error") {
    if (!errorBox) return;
    errorBox.textContent = text || "";
    errorBox.className = kind === "success" ? "form-success" : "form-error";
  }

  function redirectIfAuthenticated() {
    if (window.AdminAuth && AdminAuth.getToken()) {
      window.location.replace(AdminAuth.getDashboardPath());
      return true;
    }
    return false;
  }

  if (!redirectIfAuthenticated() && form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      setMessage("");
      const data = new FormData(form);
      const username = (data.get("username") || "").trim();
      const password = (data.get("password") || "").trim();
      if (!username || !password) {
        setMessage("Укажите логин и пароль");
        return;
      }
      submitBtn && (submitBtn.disabled = true);
      submitBtn && submitBtn.classList.add("is-disabled");
      try {
        const response = await fetch("/api/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        if (!response.ok) {
          let detail = "Ошибка авторизации";
          try {
            const payload = await response.json();
            detail = payload?.detail?.failure_reason || detail;
          } catch (err) {
            /* ignore */
          }
          throw new Error(detail);
        }
        const payload = await response.json();
        if (payload && payload.access_token) {
          AdminAuth.saveToken(payload.access_token);
          setMessage("Успешный вход", "success");
          setTimeout(() => {
            window.location.replace(AdminAuth.getDashboardPath());
          }, 300);
        } else {
          throw new Error("Сервер вернул пустой токен");
        }
      } catch (error) {
        setMessage(error?.message || "Не удалось выполнить вход");
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.classList.remove("is-disabled");
        }
      }
    });
  }

  if (toggleBtn && passwordInput) {
    toggleBtn.addEventListener("click", () => {
      const isHidden = passwordInput.type === "password";
      passwordInput.type = isHidden ? "text" : "password";
      toggleBtn.setAttribute("aria-pressed", String(isHidden));
      toggleBtn.textContent = isHidden ? "Скрыть пароль" : "Показать пароль";
    });
  }
})();
