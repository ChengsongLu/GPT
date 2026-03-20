const state = {
  currentView: "config",
  branches: [],
  currentBranch: null,
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

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
  });
}

function toISOOrNull(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
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
    setStatus(document.querySelector("#sync-status"), "正在同步 commits...");
    const result = await requestJSON("/api/sync/commits", { method: "POST" });
    setStatus(
      document.querySelector("#sync-status"),
      `已同步 ${result.commit_count} 条 commits，覆盖 ${result.branch_count} 个分支`,
    );
    setBoxContent(
      resultBox,
      `分支数：${result.branch_count}<br>新增 commits：${result.commit_count}<br>同步时间：${formatDate(result.synced_at)}`,
    );
    await loadBranchesAndCommits();
    selectView("commits");
  } catch (error) {
    setStatus(document.querySelector("#sync-status"), `同步失败：${error.message}`, true);
    setBoxContent(resultBox, "commit 同步失败。", true);
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

  const dateFrom = toISOOrNull(String(data.get("date_from") || ""));
  const dateTo = toISOOrNull(String(data.get("date_to") || ""));
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

  document.querySelector("#gitlab-form").addEventListener("submit", saveGitLabSettings);
  document.querySelector("#feishu-form").addEventListener("submit", saveFeishuSettings);
  document.querySelector("#test-gitlab-button").addEventListener("click", testGitLabConnection);
  document.querySelector("#sync-branches-button").addEventListener("click", syncBranches);
  document.querySelector("#sync-commits-button").addEventListener("click", syncCommits);

  try {
    await loadSettings();
    await loadBranchesAndCommits();
  } catch (error) {
    setStatus(document.querySelector("#page-status"), `初始化失败：${error.message}`, true);
  }
});
