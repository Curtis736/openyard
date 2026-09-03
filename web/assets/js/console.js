(() => {
  const toastEl = document.getElementById("toast");
  const statsEl = document.getElementById("stats");
  const bodyEl = document.getElementById("workloads-body");
  const form = document.getElementById("create-form");
  const refreshBtn = document.getElementById("refresh-btn");
  const modal = document.getElementById("modal");
  const modalTitle = document.getElementById("modal-title");
  const modalBody = document.getElementById("modal-body");
  const modalClose = document.getElementById("modal-close");

  function toast(message, isError = false) {
    toastEl.textContent = message;
    toastEl.classList.toggle("error", isError);
    toastEl.classList.add("show");
    window.clearTimeout(toast._t);
    toast._t = window.setTimeout(() => toastEl.classList.remove("show"), 3200);
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
      },
      ...options,
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
    const res = await fetch(path, { headers: { Accept: "application/yaml, text/plain, */*" } });
    const text = await res.text();
    if (!res.ok) throw new Error(text || res.statusText);
    return text;
  }

  function statusClass(status) {
    const s = (status || "registered").toLowerCase();
    if (s.includes("ready")) return "status-ready";
    if (s.includes("deploy")) return "status-deploying";
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

  async function loadStats() {
    try {
      const s = await api("/stats");
      const on = Boolean(s.cluster_mode);
      statsEl.innerHTML = `
        <span class="chip"><strong>${s.workloads}</strong> workloads</span>
        <span class="chip"><strong>${s.pods_ready}/${s.pods_desired}</strong> pods</span>
        <span class="chip ${on ? "chip-ok" : "chip-off"}"><strong>${on ? "cluster ON" : "cluster OFF"}</strong></span>
      `;
    } catch (err) {
      statsEl.innerHTML = `<span class="chip chip-off">${err.message}</span>`;
    }
  }

  function renderRows(items) {
    if (!items.length) {
      bodyEl.innerHTML = `<tr><td colspan="4" class="empty">Aucun workload. Crée-en un à gauche.</td></tr>`;
      return;
    }
    bodyEl.innerHTML = items
      .map((w) => {
        const status = w.status || "registered";
        return `
        <tr data-name="${w.name}">
          <td>
            <div class="name">${w.name}</div>
            <div class="image">${w.image}</div>
          </td>
          <td><span class="status ${statusClass(status)}">${status}</span></td>
          <td class="mono">${w.ready_replicas ?? 0}/${w.replicas ?? "—"}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-ghost btn-sm" data-action="apply" type="button">Apply</button>
              <button class="btn btn-ghost btn-sm" data-action="status" type="button">Status</button>
              <button class="btn btn-ghost btn-sm" data-action="manifest" type="button">YAML</button>
              <button class="btn btn-danger btn-sm" data-action="delete" type="button">Supprimer</button>
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

  async function refresh() {
    await Promise.all([loadStats(), loadWorkloads()]);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: form.name.value.trim(),
      image: form.image.value.trim(),
      port: Number(form.port.value),
      replicas: Number(form.replicas.value),
    };
    try {
      await api("/workloads", { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      form.port.value = "8080";
      form.replicas.value = "1";
      toast(`Workload « ${payload.name} » créé`);
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  });

  bodyEl.addEventListener("click", async (e) => {
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

  refreshBtn.addEventListener("click", () => refresh().catch((err) => toast(err.message, true)));
  modalClose.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  refresh().catch((err) => {
    bodyEl.innerHTML = `<tr><td colspan="4" class="empty">${err.message}</td></tr>`;
    toast(err.message, true);
  });
})();
