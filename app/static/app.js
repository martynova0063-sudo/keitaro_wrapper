const $ = (s) => document.querySelector(s);

let offersCache = [];

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) {
    const msg = typeof data.detail === "string" ? data.detail : (data.detail ? JSON.stringify(data.detail) : res.statusText);
    throw new Error(msg);
  }
  return data;
}

function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 5000);
}

/* ---------- табы ---------- */
$("#tab-create").onclick = () => switchTab("create");
$("#tab-editor").onclick = () => switchTab("editor");

function switchTab(name) {
  $("#tab-create").classList.toggle("active", name === "create");
  $("#tab-editor").classList.toggle("active", name === "editor");
  $("#panel-create").classList.toggle("hidden", name !== "create");
  $("#panel-editor").classList.toggle("hidden", name !== "editor");
}

/* ---------- каталог офферов ---------- */
async function loadOffers() {
  offersCache = await api("/api/offers");
  const list = Array.isArray(offersCache) ? offersCache : (offersCache.offers || []);
  offersCache = list;
  const fill = (sel) => {
    sel.innerHTML = '<option value="">— выберите оффер —</option>' +
      list.map((o) => `<option value="${o.id}">#${o.id} — ${o.name ?? ""}</option>`).join("");
  };
  fill($("#c-offer"));
  fill($("#a-offer"));
  $("#c-offer-count").textContent = `Доступно офферов: ${list.length}`;
}

/* ---------- создание кампании ---------- */
$("#create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    name: $("#c-name").value.trim(),
    geo_code: $("#c-geo").value.trim().toUpperCase(),
    offer_id: parseInt($("#c-offer").value, 10),
  };
  if (!body.offer_id) return toast("Выберите оффер", true);
  try {
    const res = await api("/api/campaigns", { method: "POST", body: JSON.stringify(body) });
    const c = res.campaign;
    $("#r-name").textContent = c.name;
    $("#r-id").textContent = c.id;
    $("#r-streams").innerHTML = res.streams.map((s) =>
      `<li>Поток «${s.name}» (id ${s.id}) — ${s.schema}${s.filters ? ", фильтр: " + JSON.stringify(s.filters) : ""}</li>`).join("");
    const link = $("#r-link");
    link.href = res.admin_url;
    $("#create-result").classList.remove("hidden");
    toast(`Кампания #${c.id} создана`);
    loadCampaigns();
  } catch (err) {
    toast("Ошибка: " + err.message, true);
  }
});

/* ---------- редактор ---------- */
async function loadCampaigns() {
  const data = await api("/api/campaigns");
  const list = Array.isArray(data) ? data : (data.campaigns || []);
  const sel = $("#e-campaign");
  sel.innerHTML = '<option value="">— выберите кампанию —</option>' +
    list.map((c) => `<option value="${c.id}">#${c.id} — ${c.name}</option>`).join("");
}

$("#e-campaign").addEventListener("change", () => {
  const id = parseInt($("#e-campaign").value, 10);
  if (id) loadCampaign(id); else $("#e-meta").textContent = "";
});

async function loadCampaign(id) {
  try {
    const detail = await api(`/api/campaigns/${id}`);
    const c = detail.campaign;
    $("#e-meta").innerHTML =
      `Домен: ${detail.meta.domain ?? "—"} · Группа: ${detail.meta.group ?? "—"} · ` +
      `Источник: ${detail.meta.traffic_source ?? "—"} · ` +
      `<a href="${detail.admin_url}" target="_blank" rel="noopener">открыть в админке</a>`;

    const offersStream = detail.streams.find((s) => s.schema === "landings");
    $("#e-stream-name").textContent = offersStream ? `«${offersStream.name}»` : "";
    $("#e-offers-card").classList.toggle("hidden", !offersStream);
    if (offersStream) renderOffers(offersStream.offers || []);
    else renderOffers([]);
  } catch (err) {
    toast("Ошибка: " + err.message, true);
  }
}

function renderOffers(offers) {
  const tbody = $("#e-offers-table tbody");
  const total = offers.reduce((s, o) => s + (Number(o.share) || 0), 0);
  if (!offers.length) {
    tbody.innerHTML = "";
    $("#e-empty").classList.remove("hidden");
    return;
  }
  $("#e-empty").classList.add("hidden");
  tbody.innerHTML = offers.map((o) => {
    const w = Number(o.share) || 0;
    const pct = total > 0 ? (w / total * 100).toFixed(1) : "0.0";
    return `<tr>
      <td>${o.name ?? "#" + o.offer_id}</td>
      <td>${o.offer_id}</td>
      <td>${w}</td>
      <td>${pct}%</td>
      <td>${o.state ?? "active"}</td>
      <td><button class="remove" data-id="${o.offer_id}">Удалить</button></td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll("button.remove").forEach((btn) => {
    btn.onclick = () => removeOffer(parseInt(btn.dataset.id, 10));
  });
}

$("#add-offer-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = parseInt($("#e-campaign").value, 10);
  const offerId = parseInt($("#a-offer").value, 10);
  const shareRaw = $("#a-share").value.trim();
  if (!id) return toast("Выберите кампанию", true);
  if (!offerId) return toast("Выберите оффер", true);
  const body = { offer_id: offerId };
  if (shareRaw !== "") body.share = parseFloat(shareRaw);
  try {
    await api(`/api/campaigns/${id}/offers`, { method: "POST", body: JSON.stringify(body) });
    $("#a-share").value = "";
    toast("Оффер добавлен");
    loadCampaign(id);
  } catch (err) {
    toast("Ошибка: " + err.message, true);
  }
});

async function removeOffer(offerId) {
  const id = parseInt($("#e-campaign").value, 10);
  try {
    await api(`/api/campaigns/${id}/offers/${offerId}`, { method: "DELETE" });
    toast("Оффер удалён, доля перераспределена");
    loadCampaign(id);
  } catch (err) {
    toast("Ошибка: " + err.message, true);
  }
}

/* ---------- init ---------- */
loadOffers().catch((e) => toast("Не удалось загрузить офферы: " + e.message, true));
loadCampaigns().catch((e) => toast("Не удалось загрузить кампании: " + e.message, true));
