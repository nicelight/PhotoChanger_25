(function (window) {
  const TOKEN_KEY = "photochanger.jwt";

  function datasetValue(key, fallback) {
    if (document && document.body && document.body.dataset && document.body.dataset[key]) {
      return document.body.dataset[key];
    }
    return fallback;
  }

  function getLoginPath() {
    return datasetValue("loginPath", "/ui/static/admin/login.html");
  }

  function getDashboardPath() {
    return datasetValue("dashboardPath", "/ui/static/admin/dashboard.html");
  }

  function saveToken(token) {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
    } catch (err) {
      console.warn("Unable to persist token", err);
    }
  }

  function getToken() {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch (err) {
      return null;
    }
  }

  function clearToken() {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch (err) {
      console.warn("Unable to clear token", err);
    }
  }

  function requireToken() {
    const token = getToken();
    if (!token) {
      window.location.replace(getLoginPath());
      throw new Error("AUTH_REQUIRED");
    }
    return token;
  }

  async function authFetch(input, init = {}) {
    const token = getToken();
    const headers = new Headers(init.headers || {});
    if (token) {
      headers.set("Authorization", "Bearer " + token);
    }
    const config = { ...init, headers };
    const response = await fetch(input, config);
    if (response.status === 401 || response.status === 403) {
      clearToken();
      if (!config.skipRedirect) {
        window.location.replace(getLoginPath());
      }
      throw new Error("AUTH_REQUIRED");
    }
    return response;
  }

  window.AdminAuth = {
    TOKEN_KEY,
    saveToken,
    getToken,
    clearToken,
    requireToken,
    authFetch,
    getLoginPath,
    getDashboardPath,
  };
})(window);
