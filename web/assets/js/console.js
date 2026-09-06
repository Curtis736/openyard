(() => {
  const KEY_STORAGE = "openyard.apiKey";
  const PROJECT_STORAGE = "openyard.project";
  const toastEl = document.getElementById("toast");
  const statsEl = document.getElementById("stats");
  const overviewStats = document.getElementById("overview-stats");
  const bodyEl = document.getElementById("workloads-body");
  const form = document.getElementById("create-form");
  const refreshBtn = document.getElementById("refresh-btn");
  const projectForm = document.getElementById("project-form");
  const projectsBody = document.getElementById("projects-body");
  const projectSelect = document.getElementById("project-select");
  const prefreshBtn = document.getElementById("prefresh-btn");
  const instanceForm = document.getElementById("instance-form");
  const instancesBody = document.getElementById("instances-body");
  const instanceStats = document.getElementById("instance-stats");
  const irefreshBtn = document.getElementById("irefresh-btn");
  const driverHint = document.getElementById("driver-hint");
  const apiKeyInput = document.getElementById("api-key");
  const saveKeyBtn = document.getElementById("save-key-btn");
  const authChip = document.getElementById("auth-chip");
  const pollChip = document.getElementById("poll-chip");
  const modal = document.getElementById("modal");
  const modalTitle = document.getElementById("modal-title");
  const modalBody = document.getElementById("modal-body");
  const modalClose = document.getElementById("modal-close");
  const presetWeb = document.getElementById("preset-web");
  const presetVm = document.getElementById("preset-vm");

  let pollTimer = null;
  let projectKeys = {};

  function getApiKey() {
    return (apiKeyInput?.value || localStorage.getItem(KEY_STORAGE) || "").trim();
  }

  function authHeaders(extra = {}) {
    const headers = { ...extra };
    const key = getApiKey();
    if (key) headers["X-API-Key"] = key;
    return headers;
  }

  function toast(message, isError = false) {
    toastEl.textContent = message;
    toastEl.classList.toggle("error", isError);
    toastEl.classList.add("show");
    window.clearTimeout(toast._t);
    toast._t = window.setTimeout(() => toastEl.classList.remove("show"), 3600);
  }

  async function api(path, options = {}) {
    const { headers: optHeaders, ...rest } = options;
    const res = await fetch(path, {
      ...rest,
      headers: authHeaders({
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...optHeaders,
      }),
    });
    if (res.status === 204) return null;
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    if (!res.ok) {
      const detail = data?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || d).join(", ")
            : res.statusText;
      throw new Error(msg || `HTTP ${res.status}`);
    }
    return data;
  }

  async function fetchText(path) {
    const res = await fetch(path, {
      headers: authHeaders({ Accept: "application/yaml, text/plain, */*" }),
    });
    const text = await res.text();
    if (!res.ok) throw new Error(text || res.statusText);
    return text;
  }

  function statusClass(status) {
    const s = (status || "").toLowerCase();
    if (s.includes("ready") || s === "running") return "status-ready";
    if (s.includes("deploy") || s === "pending") return "status-deploying";
    return "status-registered";
  }

  function openModal(title, content) {
    modalTitle.textContent = title;
    modalBody.textContent = content;
    modal.hidden = false;
    modal.classList.add("open");
  }

  function closeModal() {
    modal.classList.remove("open");
    modal.hidden = true;
  }

  function switchTab(target) {
    document.querySelectorAll(".tab").forEach((t) => {
      const on = t.dataset.tab === target;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll("[data-panel]").forEach((panel) => {
      const on = panel.dataset.panel === target;
      panel.hidden = !on;
      panel.classList.toggle("is-hidden", !on);
    });
  }

  async function loadAuthChip() {
    try {
      const h = await fetch("/health").then((r) => r.json());
      if (h.auth_required) {
        authChip.textContent = getApiKey() ? "auth ON" : "clé requise";
        authChip.className = `chip ${getApiKey() ? "chip-ok" : "chip-off"}`;
      } else {
        authChip.textContent = getApiKey() ? "projet key" : "default";
        authChip.className = "chip chip-ok";
      }
    } catch {
      authChip.textContent = "auth ?";
      authChip.className = "chip chip-off";
    }
  }

  function renderOverview(s) {
    if (!overviewStats) return;
    const on = Boolean(s.cluster_mode);
    overviewStats.innerHTML = `
      <span class="chip"><strong>${s.projects ?? 0}</strong> projets</span>
      <span class="chip"><strong>${s.workloads}</strong> workloads</span>
      <span class="chip"><strong>${s.pods_ready}/${s.pods_desired}</strong> pods</span>
      <span class="chip"><strong>${s.instances_running}/${s.instances}</strong> VM</span>
      <span class="chip ${on ? "chip-ok" : "chip-off"}"><strong>${on ? "cluster ON" : "cluster OFF"}</strong></span>
      <span class="chip"><strong>${s.compute_driver}</strong> compute</span>
    `;
  }

  async function loadStats() {
    try {
      const s = await api("/stats");
      const on = Boolean(s.cluster_mode);
      if (driverHint) driverHint.textContent = s.compute_driver || "sim";
      renderOverview(s);
      if (statsEl) {
        statsEl.innerHTML = `
          <span class="chip"><strong>${s.workloads}</strong> workloads</span>
          <span class="chip"><strong>${s.pods_ready}/${s.pods_desired}</strong> pods</span>
          <span class="chip ${on ? "chip-ok" : "chip-off"}"><strong>${on ? "cluster ON" : "cluster OFF"}</strong></span>
        `;
      }
      if (instanceStats) {
        instanceStats.innerHTML = `
          <span class="chip"><strong>${s.instances_running}/${s.instances}</strong> running</span>
          <span class="chip"><strong>${s.compute_driver}</strong> driver</span>
        `;
      }
    } catch (err) {
      if (statsEl) statsEl.innerHTML = `<span class="chip chip-off">${err.message}</span>`;
      if (overviewStats) overviewStats.innerHTML = `<span class="chip chip-off">${err.message}</span>`;
    }
  }

  function fillProjectSelect(items) {
    if (!projectSelect) return;
    const current = localStorage.getItem(PROJECT_STORAGE) || projectSelect.value || "default";
    projectSelect.innerHTML = items
      .map((p) => `<option value="${p.name}">${p.name} · ${p.namespace}</option>`)
      .join("");
    if ([...projectSelect.options].some((o) => o.value === current)) {
      projectSelect.value = current;
    }
  }

  function renderRows(items) {
    if (!items.length) {
      bodyEl.innerHTML = `<tr><td colspan="4" class="empty">Aucun workload. Crée-en un à gauche ou via Vue d’ensemble.</td></tr>`;
      return;
    }
    bodyEl.innerHTML = items
      .map((w) => {
        const status = w.status || "registered";
        return `
        <tr data-name="${w.name}">
          <td>
            <div class="name">${w.name}</div>
            <div class="image">${w.project} · ${w.image}</div>
            ${w.url ? `<div class="image"><a href="${w.url}" target="_blank" rel="noreferrer">${w.url}</a></div>` : ""}
          </td>
          <td><span class="status ${statusClass(status)}">${status}</span></td>
          <td class="mono">${w.ready_replicas ?? 0}/${w.replicas ?? "—"}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-ghost btn-sm" data-action="apply" type="button">Apply</button>
              <button class="btn btn-ghost btn-sm" data-action="status" type="button">Status</button>
              <button class="btn btn-ghost btn-sm" data-action="manifest" type="button">YAML</button>
              <button class="btn btn-ghost btn-sm" data-action="events" type="button">Events</button>
              <button class="btn btn-ghost btn-sm" data-action="logs" type="button">Logs</button>
              <button class="btn btn-danger btn-sm" data-action="delete" type="button">Supprimer</button>
            </div>
          </td>
        </tr>`;
      })
      .join("");
  }

  function renderInstances(items) {
    if (!items.length) {
      instancesBody.innerHTML = `<tr><td colspan="4" class="empty">Aucune VM. Lance-en une à gauche.</td></tr>`;
      return;
    }
    instancesBody.innerHTML = items
      .map((i) => {
        const status = i.status || "pending";
        return `
        <tr data-name="${i.name}">
          <td>
            <div class="name">${i.name}</div>
            <div class="image">${i.project} · linux/${i.distro} · ${i.image} · ${i.vcpus} vCPU · ${i.memory_mb} MiB</div>
          </td>
          <td><span class="status ${statusClass(status)}">${status}</span></td>
          <td class="mono">${i.ipv4 || "—"}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-ghost btn-sm" data-iaction="start" type="button">Start</button>
              <button class="btn btn-ghost btn-sm" data-iaction="stop" type="button">Stop</button>
              <button class="btn btn-ghost btn-sm" data-iaction="status" type="button">Status</button>
              <button class="btn btn-danger btn-sm" data-iaction="delete" type="button">Supprimer</button>
            </div>
          </td>
        </tr>`;
      })
      .join("");
  }

  async function loadProjects() {
    const items = await api("/projects");
    fillProjectSelect(items);
    if (!projectsBody) return;
    projectsBody.innerHTML = items
      .map((p) => {
        return `
        <tr data-name="${p.name}">
          <td>
            <div class="name">${p.name}</div>
            <div class="image">${p.message || ""}</div>
          </td>
          <td class="mono">${p.namespace}</td>
          <td class="mono">${p.pods_used}/${p.pods_quota} pods · ${p.instances_used ?? 0}/${p.instances_quota ?? 5} VM</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-ghost btn-sm" data-paction="use" type="button">Utiliser</button>
              ${
                p.name !== "default"
                  ? `<button class="btn btn-danger btn-sm" data-paction="delete" type="button">Supprimer</button>`
                  : `<span class="chip">bootstrap</span>`
              }
            </div>
          </td>
        </tr>`;
      })
      .join("");
  }

  async function loadWorkloads() {
    const items = await api("/workloads");
    renderRows(Array.isArray(items) ? items : []);
  }

  async function loadInstances() {
    const items = await api("/instances");
    renderInstances(Array.isArray(items) ? items : []);
  }

  async function refresh() {
    await loadAuthChip();
    await Promise.all([loadStats(), loadWorkloads(), loadInstances(), loadProjects()]);
  }

  function startPolling() {
    window.clearInterval(pollTimer);
    pollTimer = window.setInterval(() => {
      refresh().catch(() => {});
    }, 5000);
    if (pollChip) {
      pollChip.textContent = "live 5s";
      pollChip.className = "chip chip-ok";
    }
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });

  document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.goto));
  });

  projectSelect?.addEventListener("change", () => {
    localStorage.setItem(PROJECT_STORAGE, projectSelect.value);
    const remembered = projectKeys[projectSelect.value];
    if (remembered && apiKeyInput) {
      apiKeyInput.value = remembered;
      localStorage.setItem(KEY_STORAGE, remembered);
    } else if (projectSelect.value === "default" && apiKeyInput) {
      apiKeyInput.value = "";
      localStorage.setItem(KEY_STORAGE, "");
    }
    refresh().catch((err) => toast(err.message, true));
  });

  projectForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: projectForm.name.value.trim(),
      pods_quota: Number(projectForm.pods_quota.value),
      instances_quota: Number(projectForm.instances_quota?.value || 5),
      cpu_quota: projectForm.cpu_quota.value.trim(),
      memory_quota: projectForm.memory_quota.value.trim(),
    };
    try {
      const created = await api("/projects", { method: "POST", body: JSON.stringify(payload) });
      projectForm.reset();
      projectForm.pods_quota.value = "10";
      if (projectForm.instances_quota) projectForm.instances_quota.value = "5";
      projectForm.cpu_quota.value = "1";
      projectForm.memory_quota.value = "1Gi";
      if (created.api_key) {
        projectKeys[created.name] = created.api_key;
        if (apiKeyInput) apiKeyInput.value = created.api_key;
        localStorage.setItem(KEY_STORAGE, created.api_key);
        localStorage.setItem(PROJECT_STORAGE, created.name);
        openModal(
          `Projet « ${created.name} » créé`,
          `Namespace: ${created.namespace}\nAPI key (conservée dans le navigateur):\n\n${created.api_key}\n\nTu peux maintenant créer workloads et VM dans cet onglet.`
        );
      }
      toast(`Projet « ${created.name} » prêt`);
      await refresh();
      if (projectSelect) projectSelect.value = created.name;
    } catch (err) {
      toast(err.message, true);
    }
  });

  projectsBody?.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-paction]");
    if (!btn) return;
    const row = btn.closest("tr[data-name]");
    const name = row?.dataset.name;
    if (!name) return;
    if (btn.dataset.paction === "use") {
      if (projectSelect) projectSelect.value = name;
      localStorage.setItem(PROJECT_STORAGE, name);
      const remembered = projectKeys[name];
      if (remembered && apiKeyInput) {
        apiKeyInput.value = remembered;
        localStorage.setItem(KEY_STORAGE, remembered);
      } else if (name === "default" && apiKeyInput) {
        apiKeyInput.value = "";
        localStorage.setItem(KEY_STORAGE, "");
      }
      toast(`Projet actif : ${name}`);
      await refresh().catch((err) => toast(err.message, true));
      return;
    }
    if (name === "default") return;
    if (!window.confirm(`Supprimer le projet « ${name} » et ses ressources ?`)) return;
    try {
      await api(`/projects/${encodeURIComponent(name)}`, { method: "DELETE" });
      toast(`Projet supprimé : ${name}`);
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  });

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: form.name.value.trim(),
      image: form.image.value.trim(),
      port: Number(form.port.value),
      replicas: Number(form.replicas.value),
      apply: Boolean(form.apply?.checked),
    };
    try {
      const created = await api("/workloads", { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      form.image.value = "nginxinc/nginx-unprivileged:1.27-alpine";
      form.port.value = "8080";
      form.replicas.value = "1";
      form.apply.checked = true;
      toast(`Workload « ${payload.name} » · ${created.status}${created.url ? " · " + created.url : ""}`);
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  });

  instanceForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: instanceForm.name.value.trim(),
      image: instanceForm.image.value.trim(),
      vcpus: Number(instanceForm.vcpus.value),
      memory_mb: Number(instanceForm.memory_mb.value),
      ssh_authorized_key: (instanceForm.ssh_authorized_key?.value || "").trim(),
      launch: true,
    };
    try {
      const created = await api("/instances", { method: "POST", body: JSON.stringify(payload) });
      instanceForm.reset();
      instanceForm.image.value = "ubuntu-22.04";
      instanceForm.vcpus.value = "1";
      instanceForm.memory_mb.value = "1024";
      toast(`VM Linux « ${created.name} » · ${created.status}`);
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  });

  presetWeb?.addEventListener("click", async () => {
    const name = `web-${Date.now().toString(36).slice(-4)}`;
    try {
      const created = await api("/workloads", {
        method: "POST",
        body: JSON.stringify({
          name,
          image: "nginxinc/nginx-unprivileged:1.27-alpine",
          port: 8080,
          replicas: 1,
          apply: true,
        }),
      });
      toast(`Déployé « ${name} » · ${created.status}`);
      switchTab("workloads");
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  });

  presetVm?.addEventListener("click", async () => {
    const name = `vm-${Date.now().toString(36).slice(-4)}`;
    try {
      const created = await api("/instances", {
        method: "POST",
        body: JSON.stringify({
          name,
          image: "ubuntu-22.04",
          vcpus: 1,
          memory_mb: 1024,
          launch: true,
        }),
      });
      toast(`VM « ${name} » · ${created.status}`);
      switchTab("instances");
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  });

  bodyEl?.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const row = btn.closest("tr[data-name]");
    const name = row?.dataset.name;
    if (!name) return;
    const action = btn.dataset.action;
    try {
      if (action === "apply") {
        btn.disabled = true;
        await api(`/workloads/${encodeURIComponent(name)}/apply`, { method: "POST" });
        toast(`Apply lancé pour ${name}`);
        await refresh();
      } else if (action === "status") {
        const st = await api(`/workloads/${encodeURIComponent(name)}/status`);
        openModal(`Statut — ${name}`, JSON.stringify(st, null, 2));
      } else if (action === "manifest") {
        const yaml = await fetchText(`/workloads/${encodeURIComponent(name)}/manifest`);
        openModal(`Manifest — ${name}`, yaml);
      } else if (action === "events") {
        const events = await api(`/workloads/${encodeURIComponent(name)}/events`);
        const lines = (events || [])
          .map(
            (e) =>
              `${e.last_timestamp || "-"}\t${e.type}\t${e.reason}\t${e.involved_kind}/${e.involved_name}\t${e.message}`
          )
          .join("\n");
        openModal(`Events — ${name}`, lines || "(aucun event)"); // one event per line
      } else if (action === "logs") {
        const logs = await fetchText(`/workloads/${encodeURIComponent(name)}/logs?tail=200`);
        openModal(`Logs — ${name}`, logs || "(vide)"); // text/plain
      } else if (action === "delete") {
        if (!window.confirm(`Supprimer le workload « ${name} » ?`)) return;
        await api(`/workloads/${encodeURIComponent(name)}`, { method: "DELETE" });
        toast(`Supprimé : ${name}`);
        await refresh();
      }
    } catch (err) {
      toast(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  instancesBody?.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-iaction]");
    if (!btn) return;
    const row = btn.closest("tr[data-name]");
    const name = row?.dataset.name;
    if (!name) return;
    const action = btn.dataset.iaction;
    try {
      btn.disabled = true;
      if (action === "start") {
        await api(`/instances/${encodeURIComponent(name)}/start`, { method: "POST" });
        toast(`Start ${name}`);
        await refresh();
      } else if (action === "stop") {
        await api(`/instances/${encodeURIComponent(name)}/stop`, { method: "POST" });
        toast(`Stop ${name}`);
        await refresh();
      } else if (action === "status") {
        const st = await api(`/instances/${encodeURIComponent(name)}/status`);
        openModal(`Instance — ${name}`, JSON.stringify(st, null, 2));
      } else if (action === "delete") {
        if (!window.confirm(`Supprimer l’instance « ${name} » ?`)) return;
        await api(`/instances/${encodeURIComponent(name)}`, { method: "DELETE" });
        toast(`Instance supprimée : ${name}`);
        await refresh();
      }
    } catch (err) {
      toast(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  if (apiKeyInput) {
    apiKeyInput.value = localStorage.getItem(KEY_STORAGE) || "";
  }
  saveKeyBtn?.addEventListener("click", () => {
    localStorage.setItem(KEY_STORAGE, getApiKey());
    toast("Clé enregistrée — ressources du projet chargées");
    refresh().catch((err) => toast(err.message, true));
  });

  refreshBtn?.addEventListener("click", () => refresh().catch((err) => toast(err.message, true)));
  irefreshBtn?.addEventListener("click", () => refresh().catch((err) => toast(err.message, true)));
  prefreshBtn?.addEventListener("click", () => refresh().catch((err) => toast(err.message, true)));
  modalClose?.addEventListener("click", closeModal);
  modal?.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  const imageInput = document.getElementById("image");
  if (imageInput && !document.getElementById("image-policy-hint")) {
    const hint = document.createElement("p");
    hint.id = "image-policy-hint";
    hint.className = "hint";
    hint.textContent =
      "Images : préfixes allowlist (nginxinc/, nginx:, …) — tag requis, :latest refusé.";
    imageInput.insertAdjacentElement("afterend", hint);
  }

  refresh()
    .then(startPolling)
    .catch((err) => {
      if (bodyEl) bodyEl.innerHTML = `<tr><td colspan="4" class="empty">${err.message}</td></tr>`;
      toast(err.message, true);
      startPolling();
    });
})();
