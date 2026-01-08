(function () {
  const root = document.body;
  const overviewEndpoint = root.dataset.overviewEndpoint;
  const slotsEndpoint = root.dataset.slotsEndpoint;
  if (!overviewEndpoint || !slotsEndpoint) {
    console.warn("Stats page is missing API endpoints.");
    return;
  }

  const windowInput = document.getElementById("window-minutes");
  const refreshButton = document.getElementById("refresh-button");
  const tableRefreshButton = document.getElementById("table-refresh");
  const loadingNotice = document.getElementById("stats-loading");
  const loadingWindowLabel = document.getElementById("loading-window-label");
  const errorBox = document.getElementById("stats-error");
  const lastRefreshEl = document.getElementById("last-refresh");
  const summaryWindowChip = document.getElementById("summary-window");
  const summaryValues = {
    jobsTotal: document.getElementById("summary-jobs-total"),
    jobsWindow: document.getElementById("summary-jobs-window"),
    timeouts: document.getElementById("summary-timeouts"),
    providerErrors: document.getElementById("summary-provider-errors"),
    storage: document.getElementById("summary-storage"),
  };
  const tableBody = document.getElementById("slots-table-body");
  const failuresBody = document.getElementById("failures-table-body");
  const chartList = document.getElementById("slots-chart");

  const numberFormatter = new Intl.NumberFormat("ru-RU");
  const percentFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });
  const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
  });

  const TOKEN_KEY = "photochanger.jwt";

  const readToken = () => {
    try {
      if (!window.localStorage) {
        return null;
      }
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  };

  const clampWindow = (value) => {
    const min = Number(windowInput.min) || 5;
    const max = Number(windowInput.max) || 240;
    const numeric = Number(value) || min;
    return Math.min(Math.max(numeric, min), max);
  };

  const setButtonsDisabled = (isDisabled) => {
    refreshButton.disabled = isDisabled;
    tableRefreshButton.disabled = isDisabled;
  };

  const formatNumber = (value) => numberFormatter.format(value ?? 0);

  const formatPercent = (fraction) => {
    if (!Number.isFinite(fraction)) return "0%";
    return `${percentFormatter.format(Math.max(fraction * 100, 0))}%`;
  };

  const formatDate = (value) => {
    if (!value) return "—";
    try {
      return dateFormatter.format(new Date(value));
    } catch {
      return value;
    }
  };

  const renderSummary = (overview) => {
    const { system, window_minutes: windowMinutes } = overview;
    summaryValues.jobsTotal.textContent = formatNumber(system.jobs_total);
    summaryValues.jobsWindow.textContent = formatNumber(system.jobs_last_window);
    summaryValues.timeouts.textContent = formatNumber(system.timeouts_last_window);
    summaryValues.providerErrors.textContent = formatNumber(system.provider_errors_last_window);
    const storageValue = Number(system.storage_usage_mb ?? 0);
    summaryValues.storage.textContent = `${storageValue.toFixed(1)} МБ`;
    summaryWindowChip.textContent = `Окно ${windowMinutes} мин`;
  };

  const renderTable = (slots) => {
    if (!slots.length) {
      tableBody.innerHTML = `<tr><td colspan="8" class="muted-hint">Нет активных слотов за выбранное окно.</td></tr>`;
      return;
    }

    const rows = slots
      .map((slot) => {
        const successRate = formatPercent(slot.success_rate);
        const timeoutRate = formatPercent(slot.timeout_rate);
        return `
          <tr>
            <td>
              <strong>${slot.display_name}</strong>
              <div class="muted-hint">${slot.slot_id}</div>
            </td>
            <td>${formatNumber(slot.jobs_last_window)}</td>
            <td>${formatNumber(slot.success_last_window)}</td>
            <td>${formatNumber(slot.timeouts_last_window)}</td>
            <td>${successRate}</td>
            <td>${timeoutRate}</td>
            <td>${formatDate(slot.last_success_at)}</td>
            <td>${slot.last_error_reason ?? "—"}</td>
          </tr>
        `;
      })
      .join("");

    tableBody.innerHTML = rows;
  };

  const renderChart = (slots) => {
    if (!slots.length) {
      chartList.innerHTML = `<li class="muted-hint">Нет данных для визуализации (активные слоты отсутствуют).</li>`;
      return;
    }

    const items = slots
      .map((slot) => {
        const successPercent = Math.max(Math.min(slot.success_rate * 100, 100), 0);
        const timeoutPercent = Math.max(Math.min(slot.timeout_rate * 100, 100), 0);
        return `
          <li class="chart-item">
            <div class="chart-item__header">
              <strong>${slot.display_name}</strong>
              <span>${formatPercent(slot.success_rate)} успеха · ${formatPercent(slot.timeout_rate)} таймаута</span>
            </div>
            <div class="chart-bar" aria-label="Доля успехов и таймаутов">
              <span class="chart-bar__success" style="width:${successPercent}%;"></span>
              <span class="chart-bar__timeouts" style="width:${timeoutPercent}%;"></span>
            </div>
          </li>
        `;
      })
      .join("");

    chartList.innerHTML = items;
  };

  const renderFailures = (failures) => {
    if (!failuresBody) {
      return;
    }
    if (!failures.length) {
      failuresBody.innerHTML = `<tr><td colspan="4" class="muted-hint">Нет ошибок за выбранное окно.</td></tr>`;
      return;
    }
    const rows = failures
      .map((item) => {
        const httpStatus = item.http_status ?? "—";
        return `
          <tr>
            <td>${formatDate(item.finished_at)}</td>
            <td>${item.slot_id ?? "—"}</td>
            <td>${httpStatus}</td>
            <td>${item.failure_reason ?? "—"}</td>
          </tr>
        `;
      })
      .join("");
    failuresBody.innerHTML = rows;
  };

  const updateTimestamp = () => {
    const now = new Date();
    lastRefreshEl.textContent = `Обновлено ${dateFormatter.format(now)}`;
  };

  const loadStats = async () => {
    const windowValue = clampWindow(windowInput.value);
    windowInput.value = windowValue;
    loadingWindowLabel.textContent = windowValue;
    loadingNotice.hidden = false;
    errorBox.hidden = true;
    errorBox.textContent = "";
    setButtonsDisabled(true);

    const query = `?window_minutes=${windowValue}`;
    const token = readToken();
    if (!token) {
      errorBox.textContent = "Требуется авторизация: войдите в систему, чтобы увидеть статистику.";
      errorBox.hidden = false;
      loadingNotice.hidden = true;
      setButtonsDisabled(false);
      return;
    }
    const authHeaders = {
      Authorization: `Bearer ${token}`,
    };
    try {
      const [overviewResp, slotsResp] = await Promise.all([
        fetch(`${overviewEndpoint}${query}`, { headers: authHeaders }),
        fetch(`${slotsEndpoint}${query}`, { headers: authHeaders }),
      ]);

      if (!overviewResp.ok) {
        throw new Error(`overview: ${overviewResp.status}`);
      }
      if (!slotsResp.ok) {
        throw new Error(`slots: ${slotsResp.status}`);
      }

      const overviewData = await overviewResp.json();
      const slotsData = await slotsResp.json();

      renderSummary(overviewData);
      renderTable(slotsData.slots || []);
      renderChart(slotsData.slots || []);
      renderFailures(slotsData.recent_failures || []);
      updateTimestamp();
    } catch (error) {
      console.error(error);
      errorBox.textContent = `Не удалось получить статистику: ${error?.message ?? error}`;
      errorBox.hidden = false;
    } finally {
      loadingNotice.hidden = true;
      setButtonsDisabled(false);
    }
  };

  refreshButton.addEventListener("click", loadStats);
  tableRefreshButton.addEventListener("click", loadStats);
  windowInput.addEventListener("change", () => {
    windowInput.value = clampWindow(windowInput.value);
  });

  document.addEventListener("DOMContentLoaded", loadStats);
})();
