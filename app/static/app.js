const state = {
  currentView: "config",
  branches: [],
  currentBranch: null,
  reportDates: [],
  selectedReportDate: null,
  logFiles: [],
  selectedLogDate: null,
  reportBranches: [],
  currentReportBranch: null,
  page: 1,
  pageSize: 20,
  total: 0,
};

async function requestJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

function fillForm(form, values) {
  for (const element of form.elements) {
    if (!(element instanceof HTMLInputElement)) continue;
    if (!Object.hasOwn(values, element.name)) continue;
    element.value = values[element.name] ?? "";
  }
}

function formDataToJSON(form) {
  const data = new FormData(form);
  return Object.fromEntries(data.entries());
}

function setStatus(target, message, isError = false) {
  target.textContent = message;
  target.dataset.state = isError ? "error" : "success";
}

function setBoxContent(target, html, isEmpty = false) {
  target.innerHTML = html;
  target.classList.toggle("empty", isEmpty);
}

function parseServerDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  const raw = String(value).trim();
  if (!raw) return null;

  // SQLite often returns naive UTC timestamps like 2026-03-20T06:34:43.
  // Treat them as UTC before rendering in Asia/Shanghai.
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(raw) ? raw : `${raw}Z`;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatDate(value) {
  if (!value) return "-";
  const parsed = parseServerDate(value);
  if (!parsed) return String(value);
  return parsed.toLocaleString("zh-CN", {
    hour12: false,
    timeZone: "Asia/Shanghai",
  });
}

function toDateTimeQueryValueOrNull(value) {
  if (!value) return null;
  return String(value).trim() || null;
}

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function updateNav() {
  document.querySelectorAll(".nav-pill").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === state.currentView);
  });

  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("is-active", section.id === `view-${state.currentView}`);
  });
}

function selectView(viewName) {
  state.currentView = viewName;
  updateNav();
}

function bindNavigation() {
  document.querySelectorAll(".nav-pill").forEach((button) => {
    button.addEventListener("click", () => {
      selectView(button.dataset.view);
      if (button.dataset.view === "commits") {
        loadBranchesAndCommits();
      }
      if (button.dataset.view === "reports") {
        loadReports();
      }
      if (button.dataset.view === "feishu") {
        loadContributors();
      }
      if (button.dataset.view === "logs") {
        loadLogs();
      }
    });
  });
}

async function loadSettings() {
  const settings = await requestJSON("/api/settings");
  fillForm(document.querySelector("#gitlab-form"), settings);
  fillForm(document.querySelector("#feishu-form"), settings);
}

async function saveGitLabSettings(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = formDataToJSON(form);
  payload.sync_interval_minutes = Number(payload.sync_interval_minutes);

  try {
    await requestJSON("/api/settings/gitlab", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setStatus(document.querySelector("#gitlab-status"), "GitLab 配置已保存");
    setStatus(document.querySelector("#page-status"), "配置已更新");
  } catch (error) {
    setStatus(document.querySelector("#gitlab-status"), `保存失败：${error.message}`, true);
  }
}

async function saveFeishuSettings(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = formDataToJSON(form);

  try {
    await requestJSON("/api/settings/feishu", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setStatus(document.querySelector("#feishu-status"), "飞书配置已保存");
  } catch (error) {
    setStatus(document.querySelector("#feishu-status"), `保存失败：${error.message}`, true);
  }
}

async function testFeishuConnection() {
  const form = document.querySelector("#feishu-form");
  const resultBox = document.querySelector("#feishu-result");
  const status = document.querySelector("#feishu-status");
  const payload = formDataToJSON(form);

  if (!String(payload.feishu_app_id || "").trim()) {
    setStatus(status, "连接失败：请先填写 Feishu App ID", true);
    setBoxContent(resultBox, "未填写 Feishu App ID。", true);
    return;
  }
  if (!String(payload.feishu_app_secret || "").trim()) {
    setStatus(status, "连接失败：请先填写 Feishu App Secret", true);
    setBoxContent(resultBox, "未填写 Feishu App Secret。", true);
    return;
  }
  if (!String(payload.feishu_bitable_app_token || "").trim()) {
    setStatus(status, "连接失败：请先填写多维表格 App Token", true);
    setBoxContent(resultBox, "未填写多维表格 App Token。", true);
    return;
  }
  if (!String(payload.feishu_bitable_table_id || "").trim()) {
    setStatus(status, "连接失败：请先填写多维表格 Table ID", true);
    setBoxContent(resultBox, "未填写多维表格 Table ID。", true);
    return;
  }

  try {
    setStatus(status, "正在测试飞书连接...");
    const result = await requestJSON("/api/settings/test-feishu", {
      method: "POST",
      body: JSON.stringify({
        feishu_app_id: String(payload.feishu_app_id).trim(),
        feishu_app_secret: String(payload.feishu_app_secret).trim(),
        feishu_base_url: String(payload.feishu_base_url || "").trim(),
        feishu_bitable_app_token: String(payload.feishu_bitable_app_token).trim(),
        feishu_bitable_table_id: String(payload.feishu_bitable_table_id).trim(),
      }),
    });
    setStatus(status, "飞书连接成功");
    setBoxContent(
      resultBox,
      `App Token：${result.app_token}<br>Table ID：${result.table_id}<br>示例记录数：${result.sample_record_count}`,
    );
  } catch (error) {
    setStatus(status, `连接失败：${error.message}`, true);
    setBoxContent(resultBox, `连接失败，请检查配置。<br>${error.message}`, true);
  }
}

async function syncFeishuContributors() {
  const resultBox = document.querySelector("#feishu-result");
  try {
    setStatus(document.querySelector("#feishu-status"), "正在同步飞书成员映射...");
    const result = await requestJSON("/api/sync/feishu-contributors", { method: "POST" });
    setStatus(
      document.querySelector("#feishu-status"),
      `已同步 ${result.synced_count} 条成员映射，激活 ${result.active_count} 条`,
    );
    const preview = result.contributors
      .slice(0, 5)
      .map((item) => `${item.name} / ${item.gitlab_username || "-"} / ${item.component || "-"}`)
      .join("<br>");
    setBoxContent(
      resultBox,
      `同步成员：${result.synced_count}<br>激活成员：${result.active_count}<br><br>${preview || "暂无成员预览"}`,
    );
    await loadContributors();
  } catch (error) {
    setStatus(document.querySelector("#feishu-status"), `同步失败：${error.message}`, true);
    setBoxContent(resultBox, `同步失败，请检查配置。<br>${error.message}`, true);
  }
}

function renderContributors(payload) {
  const summary = document.querySelector("#contributors-summary");
  const total = document.querySelector("#contributors-total");
  const active = document.querySelector("#contributors-active");
  const target = document.querySelector("#contributors-table-wrap");

  summary.textContent = `${payload.active_count} / ${payload.total_count}`;
  total.textContent = String(payload.total_count);
  active.textContent = String(payload.active_count);

  if (payload.contributors.length === 0) {
    target.className = "table-wrap empty-state";
    target.innerHTML = "尚未同步成员映射。";
    return;
  }

  target.className = "table-wrap";
  target.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>开发者姓名</th>
          <th>GitLab 用户名</th>
          <th>负责组件</th>
          <th>状态</th>
          <th>更新时间</th>
        </tr>
      </thead>
      <tbody>
        ${payload.contributors
          .map(
            (item) => `
              <tr>
                <td>${escapeHTML(item.name || "-")}</td>
                <td>${escapeHTML(item.gitlab_username || "-")}</td>
                <td>${escapeHTML(item.component || "-")}</td>
                <td>
                  <span class="status-pill ${item.is_active ? "" : "is-inactive"}">
                    ${item.is_active ? "激活" : "已停用"}
                  </span>
                </td>
                <td>${escapeHTML(formatDate(item.updated_at))}</td>
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

async function loadContributors() {
  try {
    const payload = await requestJSON("/api/contributors");
    renderContributors(payload);
    setStatus(
      document.querySelector("#contributors-status"),
      payload.total_count > 0 ? `已加载 ${payload.total_count} 条成员映射` : "当前还没有成员映射数据",
    );
  } catch (error) {
    setStatus(document.querySelector("#contributors-status"), `加载成员映射失败：${error.message}`, true);
  }
}

async function testGitLabConnection() {
  const form = document.querySelector("#gitlab-form");
  const resultBox = document.querySelector("#gitlab-test-result");
  const status = document.querySelector("#gitlab-status");

  const payload = formDataToJSON(form);
  if (!String(payload.gitlab_base_url || "").trim()) {
    setStatus(status, "连接失败：请先填写 GitLab Base URL", true);
    setBoxContent(resultBox, "未填写 GitLab Base URL。", true);
    return;
  }
  if (!String(payload.gitlab_token || "").trim()) {
    setStatus(status, "连接失败：请先填写 GitLab Token", true);
    setBoxContent(resultBox, "未填写 GitLab Token。Mock 场景也需要填任意非空字符串。", true);
    return;
  }
  if (!String(payload.gitlab_project_ref || "").trim()) {
    setStatus(status, "连接失败：请先填写 Project ID 或 group/project", true);
    setBoxContent(resultBox, "未填写项目标识。", true);
    return;
  }

  try {
    setStatus(status, "正在测试连接...");
    const result = await requestJSON("/api/settings/test-gitlab", {
      method: "POST",
      body: JSON.stringify({
        gitlab_base_url: String(payload.gitlab_base_url).trim(),
        gitlab_token: String(payload.gitlab_token).trim(),
        gitlab_project_ref: String(payload.gitlab_project_ref).trim(),
      }),
    });
    setStatus(status, "GitLab 连接成功");
    setBoxContent(
      resultBox,
      `<strong>${result.project_name}</strong><br>
       <span>${result.project_path}</span><br>
       <span>默认分支：${result.default_branch || "-"}</span><br>
       <a href="${result.web_url || "#"}" target="_blank" rel="noreferrer">打开 GitLab 项目</a>`,
    );
  } catch (error) {
    setStatus(status, `连接失败：${error.message}`, true);
    setBoxContent(resultBox, `连接失败，请检查配置。<br>${error.message}`, true);
  }
}

async function syncBranches() {
  const resultBox = document.querySelector("#sync-result");
  try {
    setStatus(document.querySelector("#sync-status"), "正在同步分支...");
    const result = await requestJSON("/api/sync/branches", { method: "POST" });
    setStatus(document.querySelector("#sync-status"), `已同步 ${result.synced_count} 个分支`);
    setBoxContent(
      resultBox,
      `默认分支：${result.default_branch || "-"}<br>同步分支数：${result.synced_count}`,
    );
    await loadBranchesAndCommits();
  } catch (error) {
    setStatus(document.querySelector("#sync-status"), `同步失败：${error.message}`, true);
    setBoxContent(resultBox, "分支同步失败。", true);
  }
}

async function syncCommits() {
  const resultBox = document.querySelector("#sync-result");
  try {
    setStatus(document.querySelector("#sync-status"), "正在全量同步 commits 历史...");
    const result = await requestJSON("/api/sync/commits?full_sync=true", { method: "POST" });
    setStatus(
      document.querySelector("#sync-status"),
      `已补齐 ${result.commit_count} 条 commits，覆盖 ${result.branch_count} 个分支`,
    );
    setBoxContent(
      resultBox,
      `分支数：${result.branch_count}<br>本次新增 commits：${result.commit_count}<br>同步时间：${formatDate(result.synced_at)}<br>模式：全量补齐历史并去重`,
    );
    await loadBranchesAndCommits();
    selectView("commits");
  } catch (error) {
    setStatus(document.querySelector("#sync-status"), `同步失败：${error.message}`, true);
    setBoxContent(resultBox, "commit 同步失败。", true);
  }
}

function renderReportItems(target, items) {
  if (items.length === 0) {
    target.innerHTML = '<div class="empty-state">当前还没有日报数据。</div>';
    return;
  }

  target.innerHTML = items
    .map(
      (item) => `
        <article class="report-item">
          <div class="commit-meta">
            <span>${escapeHTML(item.report_date)}</span>
            <span>${escapeHTML(item.status)}</span>
            <span>${escapeHTML(formatDate(item.created_at))}</span>
          </div>
          <pre>${escapeHTML(item.content)}</pre>
        </article>
      `,
    )
    .join("");
}

function renderReportBranchTabs() {
  const target = document.querySelector("#report-branch-tabs");
  if (state.reportBranches.length === 0) {
    target.innerHTML = '<div class="empty-state">当前还没有分支日报。</div>';
    return;
  }

  target.innerHTML = state.reportBranches
    .map(
      (branchName) => `
        <button
          type="button"
          class="branch-tab ${branchName === state.currentReportBranch ? "is-active" : ""}"
          data-report-branch="${escapeHTML(branchName)}">
          ${escapeHTML(branchName)}
        </button>
      `,
    )
    .join("");

  target.querySelectorAll(".branch-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.currentReportBranch = button.dataset.reportBranch;
      renderReportBranchTabs();
      loadBranchReportsOnly();
    });
  });
}

function renderReportDateSelect() {
  const target = document.querySelector("#report-date-select");
  if (state.reportDates.length === 0) {
    target.innerHTML = '<option value="">当前还没有可查看的日报日期</option>';
    target.value = "";
    return;
  }

  target.innerHTML = state.reportDates
    .map(
      (item) => `
        <option value="${escapeHTML(item.report_date)}" ${item.report_date === state.selectedReportDate ? "selected" : ""}>
          ${escapeHTML(item.report_date)} · ${item.commit_count} commits${item.has_reports ? "" : " · 未生成"}
        </option>
      `,
    )
    .join("");
}

async function loadBranchReportsOnly() {
  const target = document.querySelector("#branch-reports");
  if (!state.currentReportBranch) {
    target.innerHTML = '<div class="empty-state">当前还没有分支日报。</div>';
    return;
  }

  try {
    const params = new URLSearchParams({ branch: state.currentReportBranch });
    if (state.selectedReportDate) params.set("report_date", state.selectedReportDate);
    const payload = await requestJSON(`/api/reports?${params.toString()}`);
    renderReportItems(target, payload.items);
  } catch (error) {
    setStatus(document.querySelector("#reports-status"), `加载分支日报失败：${error.message}`, true);
  }
}

async function loadReportsForSelectedDate() {
  if (!state.selectedReportDate) {
    document.querySelector("#project-reports").innerHTML =
      '<div class="empty-state">当前还没有项目整体日报。</div>';
    document.querySelector("#branch-reports").innerHTML =
      '<div class="empty-state">当前还没有分支日报。</div>';
    document.querySelector("#report-branch-tabs").innerHTML =
      '<div class="empty-state">当前还没有分支日报。</div>';
    document.querySelector("#report-summary").textContent = "未生成";
    document.querySelector("#generate-reports-button").textContent = "重新生成选中日报";
    setStatus(document.querySelector("#reports-status"), "当前还没有可查看的日报日期", true);
    return;
  }

  try {
    const [projectPayload, branchPayload] = await Promise.all([
      requestJSON(`/api/reports/project-daily?report_date=${encodeURIComponent(state.selectedReportDate)}`),
      requestJSON(`/api/reports?report_date=${encodeURIComponent(state.selectedReportDate)}`),
    ]);

    renderReportItems(document.querySelector("#project-reports"), projectPayload.items);
    state.reportBranches = branchPayload.branch_names;
    if (
      !state.currentReportBranch ||
      !state.reportBranches.some((branchName) => branchName === state.currentReportBranch)
    ) {
      state.currentReportBranch = state.reportBranches[0] || null;
    }
    renderReportBranchTabs();
    await loadBranchReportsOnly();

    const selectedSummaryDate = state.selectedReportDate || "未选择";
    document.querySelector("#report-summary").textContent = String(selectedSummaryDate);
    document.querySelector("#generate-reports-button").textContent =
      projectPayload.items.length > 0 ? `重新生成 ${state.selectedReportDate}` : `生成 ${state.selectedReportDate}`;
    setStatus(
      document.querySelector("#reports-status"),
      projectPayload.items.length > 0 || branchPayload.items.length > 0
        ? `已加载 ${state.selectedReportDate} 的日报数据`
        : `${state.selectedReportDate} 这一天已有 commits，但还没有生成日报`,
    );
  } catch (error) {
    setStatus(document.querySelector("#reports-status"), `加载日报失败：${error.message}`, true);
  }
}

async function loadReports() {
  try {
    const payload = await requestJSON("/api/reports/dates");
    state.reportDates = payload.items;
    const hasCurrent = state.reportDates.some((item) => item.report_date === state.selectedReportDate);
    if (!state.selectedReportDate || !hasCurrent) {
      state.selectedReportDate = payload.selected_date || null;
    }
    renderReportDateSelect();
    await loadReportsForSelectedDate();
  } catch (error) {
    setStatus(document.querySelector("#reports-status"), `加载日报日期失败：${error.message}`, true);
  }
}

async function generateDailyReports() {
  if (!state.selectedReportDate) {
    setStatus(document.querySelector("#reports-status"), "当前没有可重生成的日报日期", true);
    return;
  }

  try {
    setStatus(document.querySelector("#reports-status"), `正在重新生成 ${state.selectedReportDate} 的日报...`);
    const payload = await requestJSON(
      `/api/reports/generate-daily?report_date=${encodeURIComponent(state.selectedReportDate)}`,
      { method: "POST" },
    );
    setBoxContent(
      document.querySelector("#report-result"),
      `日报日期：${payload.report_date}<br>项目 commit 数：${payload.commit_count}<br>分支日报数：${payload.branch_count}<br>如果该日期已有日报，本次结果已覆盖旧版本。`,
    );
    await loadReports();
    setStatus(
      document.querySelector("#reports-status"),
      `日报已重新生成：${payload.report_date}，共处理 ${payload.commit_count} 条 commit`,
    );
    selectView("reports");
  } catch (error) {
    setStatus(document.querySelector("#reports-status"), `生成日报失败：${error.message}`, true);
    setBoxContent(document.querySelector("#report-result"), `生成失败。<br>${error.message}`, true);
  }
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function renderLogDateSelect() {
  const target = document.querySelector("#log-date-select");
  if (state.logFiles.length === 0) {
    target.innerHTML = '<option value="">当前还没有日志文件</option>';
    target.value = "";
    document.querySelector("#logs-summary").textContent = "无日志";
    return;
  }

  target.innerHTML = state.logFiles
    .map(
      (item) => `
        <option value="${escapeHTML(item.log_date)}" ${item.log_date === state.selectedLogDate ? "selected" : ""}>
          ${escapeHTML(item.log_date)} · ${escapeHTML(formatBytes(item.size_bytes))}
        </option>
      `,
    )
    .join("");
  document.querySelector("#logs-summary").textContent = `${state.logFiles.length} 个文件`;
}

async function loadLogContent() {
  const status = document.querySelector("#logs-status");
  const meta = document.querySelector("#logs-meta");
  const content = document.querySelector("#logs-content");

  if (!state.selectedLogDate) {
    setStatus(status, "当前还没有可查看的日志文件", true);
    setBoxContent(meta, "当前还没有日志文件。", true);
    content.textContent = "当前还没有日志内容。";
    return;
  }

  try {
    const limit = Number(document.querySelector("#log-line-limit").value || 200);
    setStatus(status, `正在加载 ${state.selectedLogDate} 的日志...`);
    const payload = await requestJSON(
      `/api/logs/content?log_date=${encodeURIComponent(state.selectedLogDate)}&limit=${limit}`,
    );
    const selected = state.logFiles.find((item) => item.log_date === state.selectedLogDate);
    setBoxContent(
      meta,
      `日志文件：${escapeHTML(payload.filename)}<br>返回行数：${payload.line_count}<br>文件大小：${escapeHTML(formatBytes(selected?.size_bytes || 0))}<br>最后更新：${escapeHTML(formatDate(selected?.modified_at))}`,
    );
    content.textContent = payload.content || "日志文件存在，但当前没有内容。";
    content.classList.remove("empty-state");
    setStatus(status, `已加载 ${payload.filename} 的最近 ${payload.line_count} 行`);
  } catch (error) {
    setStatus(status, `加载日志失败：${error.message}`, true);
    setBoxContent(meta, `加载日志失败。<br>${error.message}`, true);
    content.textContent = "日志内容加载失败。";
    content.classList.add("empty-state");
  }
}

async function loadLogs() {
  try {
    const payload = await requestJSON("/api/logs");
    state.logFiles = payload.items;
    const hasCurrent = state.logFiles.some((item) => item.log_date === state.selectedLogDate);
    if (!state.selectedLogDate || !hasCurrent) {
      state.selectedLogDate = payload.selected_date || null;
    }
    renderLogDateSelect();
    await loadLogContent();
  } catch (error) {
    setStatus(document.querySelector("#logs-status"), `加载日志列表失败：${error.message}`, true);
  }
}

function renderBranchTabs() {
  const target = document.querySelector("#branch-tabs");
  if (state.branches.length === 0) {
    target.innerHTML = '<div class="empty-state">尚未同步分支。</div>';
    return;
  }

  target.innerHTML = state.branches
    .map(
      (branch) => `
        <button
          type="button"
          class="branch-tab ${branch.name === state.currentBranch ? "is-active" : ""}"
          data-branch="${branch.name}">
          ${branch.name}${branch.is_default ? " · default" : ""}
        </button>
      `,
    )
    .join("");

  target.querySelectorAll(".branch-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.currentBranch = button.dataset.branch;
      state.page = 1;
      renderBranchTabs();
      loadCommits();
    });
  });
}

async function loadBranchesAndCommits() {
  try {
    const branches = await requestJSON("/api/branches");
    state.branches = branches;
    if (!state.currentBranch || !branches.some((branch) => branch.name === state.currentBranch)) {
      state.currentBranch = branches[0]?.name || null;
    }
    renderBranchTabs();
    await loadCommits();
  } catch (error) {
    setStatus(document.querySelector("#commit-status"), `加载分支失败：${error.message}`, true);
  }
}

function buildCommitQuery() {
  const form = document.querySelector("#commit-filter-form");
  const data = new FormData(form);
  const params = new URLSearchParams();

  if (state.currentBranch) params.set("branch", state.currentBranch);
  if (data.get("author")) params.set("author", String(data.get("author")));

  const dateFrom = toDateTimeQueryValueOrNull(String(data.get("date_from") || ""));
  const dateTo = toDateTimeQueryValueOrNull(String(data.get("date_to") || ""));
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);

  state.pageSize = Number(data.get("page_size") || 20);
  params.set("page", String(state.page));
  params.set("page_size", String(state.pageSize));
  return params;
}

function renderCommitList(payload) {
  const target = document.querySelector("#commit-list");
  state.total = payload.total;

  if (payload.items.length === 0) {
    target.innerHTML = '<div class="empty-state">当前条件下没有 commits。</div>';
    document.querySelector("#commit-summary").textContent = "0 条结果";
    document.querySelector("#pagination-label").textContent = `第 ${state.page} 页`;
    return;
  }

  target.innerHTML = payload.items
    .map(
      (item) => `
        <article class="commit-item">
          <div class="commit-meta">
            <span>${item.branch_name}</span>
            <span>${item.author_name || "-"}</span>
            <span>${formatDate(item.committed_at)}</span>
          </div>
          <h3>${item.title || "(无标题)"}</h3>
          <p>${item.message || ""}</p>
          <div class="commit-footer">
            <code>${item.commit_sha.slice(0, 12)}</code>
            ${
              item.web_url
                ? `<a href="${item.web_url}" target="_blank" rel="noreferrer">打开提交</a>`
                : "<span>无链接</span>"
            }
          </div>
        </article>
      `,
    )
    .join("");

  const from = (state.page - 1) * state.pageSize + 1;
  const to = Math.min(state.total, state.page * state.pageSize);
  document.querySelector("#commit-summary").textContent = `${from}-${to} / ${state.total}`;
  document.querySelector("#pagination-label").textContent = `第 ${state.page} 页`;
}

async function loadCommits() {
  if (!state.currentBranch) {
    document.querySelector("#commit-list").innerHTML =
      '<div class="empty-state">尚未同步分支。</div>';
    document.querySelector("#commit-summary").textContent = "未加载";
    return;
  }

  try {
    setStatus(document.querySelector("#commit-status"), "正在加载 commits...");
    const params = buildCommitQuery();
    const payload = await requestJSON(`/api/commits?${params.toString()}`);
    renderCommitList(payload);
    setStatus(document.querySelector("#commit-status"), `已加载分支 ${state.currentBranch}`);
  } catch (error) {
    setStatus(document.querySelector("#commit-status"), `加载 commits 失败：${error.message}`, true);
  }
}

function bindCommitFilters() {
  document.querySelector("#commit-filter-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    state.page = 1;
    await loadCommits();
  });

  document.querySelector("#reset-commit-filters").addEventListener("click", async () => {
    const form = document.querySelector("#commit-filter-form");
    form.reset();
    form.elements.page_size.value = "20";
    state.page = 1;
    state.pageSize = 20;
    await loadCommits();
  });

  document.querySelector("#prev-page").addEventListener("click", async () => {
    if (state.page === 1) return;
    state.page -= 1;
    await loadCommits();
  });

  document.querySelector("#next-page").addEventListener("click", async () => {
    if (state.page * state.pageSize >= state.total) return;
    state.page += 1;
    await loadCommits();
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  bindNavigation();
  bindCommitFilters();
  document.querySelector("#report-date-select").addEventListener("change", async (event) => {
    state.selectedReportDate = event.currentTarget.value || null;
    state.currentReportBranch = null;
    await loadReportsForSelectedDate();
  });
  document.querySelector("#log-date-select").addEventListener("change", async (event) => {
    state.selectedLogDate = event.currentTarget.value || null;
    await loadLogContent();
  });
  document.querySelector("#log-line-limit").addEventListener("change", loadLogContent);

  document.querySelector("#gitlab-form").addEventListener("submit", saveGitLabSettings);
  document.querySelector("#feishu-form").addEventListener("submit", saveFeishuSettings);
  document.querySelector("#test-gitlab-button").addEventListener("click", testGitLabConnection);
  document.querySelector("#test-feishu-button").addEventListener("click", testFeishuConnection);
  document.querySelector("#sync-feishu-button").addEventListener("click", syncFeishuContributors);
  document.querySelector("#sync-branches-button").addEventListener("click", syncBranches);
  document.querySelector("#sync-commits-button").addEventListener("click", syncCommits);
  document.querySelector("#generate-reports-button").addEventListener("click", generateDailyReports);
  document.querySelector("#refresh-logs-button").addEventListener("click", loadLogs);

  try {
    await loadSettings();
    await loadBranchesAndCommits();
    await loadReports();
    await loadContributors();
    await loadLogs();
  } catch (error) {
    setStatus(document.querySelector("#page-status"), `初始化失败：${error.message}`, true);
  }
});
