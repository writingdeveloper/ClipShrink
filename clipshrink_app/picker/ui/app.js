/* ClipShrink Picker UI. pywebview 부재 시(mock) 브라우저 단독 미리보기 지원. */
const $ = (s) => document.querySelector(s);
const state = { items: [], recent: [], folders: [], strings: {}, tab: "emoji", query: "" };

const str = (k) => state.strings[k] || k;
const api = () => window.pywebview && window.pywebview.api;

/* ---------- 데이터 ---------- */
async function refresh() {
  if (!api()) { mock(); applyStrings(); render(); renderFolders(); return; }
  const s = await api().get_state();
  Object.assign(state, { items: s.items, recent: s.recent, folders: s.folders, strings: s.strings });
  applyStrings(); render(); renderFolders();
}

function mock() {
  const sq = (c) => "data:image/svg+xml," + encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' rx='12' fill='${c}'/></svg>`);
  state.items = [
    { id: "1", type: "emoji", name: "smile", keywords: ["happy"], animated: false, url: sq("#f9a62b"), can_url: true, is_folder: false, convert_warning: false },
    { id: "2", type: "emoji", name: "wave", keywords: [], animated: false, url: sq("#eb459e"), can_url: true, is_folder: false, convert_warning: false },
    { id: "3", type: "sticker", name: "cat", keywords: [], animated: false, url: sq("#57f287"), can_url: false, is_folder: false, convert_warning: true },
    { id: "4", type: "gif", name: "dance", keywords: [], animated: true, url: sq("#5865f2"), can_url: false, is_folder: true, convert_warning: false },
  ];
  state.recent = ["1"];
  state.folders = [{ path: "C:\\mock\\gifs", default_type: "gif", exists: true }];
  state.strings = {};
}

/* ---------- 렌더 ---------- */
function applyStrings() {
  $("#search").placeholder = str("picker_search");
  document.querySelectorAll(".tab").forEach((b) => {
    b.textContent = str("picker_tab_" + b.dataset.tab);
  });
  $("#hint").textContent = str("picker_hint");
  $("#add-title").textContent = str("picker_add_title");
  $("#add-url").placeholder = str("picker_add_url_ph");
  $("#add-name").placeholder = str("picker_add_name_ph");
  $("#add-kw").placeholder = str("picker_add_kw_ph");
  $("#add-note").textContent = str("picker_add_note");
  $("#add-submit").textContent = str("picker_add_submit");
  $("#add-cancel").textContent = str("picker_cancel");
  $("#st-title").textContent = str("picker_folders_title");
  $("#st-addfolder").textContent = str("picker_add_folder");
  $("#st-close").textContent = str("picker_cancel");
  $("#dropzone").textContent = str("picker_drop_hint");
}

// 타이핑 반응성을 위한 클라이언트 미러. 정식 검색 책임은 library.search() (스펙 §3).
function filtered() {
  const q = state.query.trim().toLowerCase();
  return state.items.filter((i) => i.type === state.tab &&
    (!q || i.name.toLowerCase().includes(q) ||
      i.keywords.some((k) => k.toLowerCase().includes(q))));
}

function render() {
  const c = $("#content");
  c.innerHTML = "";
  const items = filtered();
  if (!state.query) {
    const rset = new Set(state.recent);
    const rec = items.filter((i) => rset.has(i.id));
    if (rec.length) c.appendChild(section(str("picker_recent"), rec.slice(0, 16)));
  }
  if (!items.length) {
    const d = document.createElement("div");
    d.className = "empty";
    d.textContent = str("picker_empty");
    c.appendChild(d);
    return;
  }
  c.appendChild(section("", items));
}

function section(title, items) {
  const wrap = document.createElement("div");
  if (title) {
    const h = document.createElement("h4");
    h.textContent = title;
    wrap.appendChild(h);
  }
  const g = document.createElement("div");
  g.className = "grid " + state.tab;
  for (const item of items) {
    const b = document.createElement("button");
    b.className = "cell";
    b.title = item.name;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = item.url;
    b.appendChild(img);
    if (item.convert_warning) {
      const badge = document.createElement("span");
      badge.className = "warn-badge";
      badge.textContent = "!";
      badge.title = str("picker_convert_warn");
      b.title = item.name + " — " + str("picker_convert_warn");
      b.appendChild(badge);
    }
    b.addEventListener("click", () => select(item, "file"));
    b.addEventListener("contextmenu", (e) => { e.preventDefault(); showCtx(e, item); });
    g.appendChild(b);
  }
  wrap.appendChild(g);
  return wrap;
}

function select(item, mode) {
  if (api()) api().select_item(item.id, mode);
}

/* ---------- 컨텍스트 메뉴 ---------- */
function showCtx(e, item) {
  const ctx = $("#ctx");
  ctx.innerHTML = "";
  const add = (label, fn, danger) => {
    const b = document.createElement("button");
    b.textContent = label;
    if (danger) b.className = "danger";
    b.addEventListener("click", () => { hideCtx(); fn(); });
    ctx.appendChild(b);
  };
  add(str("picker_ctx_file"), () => select(item, "file"));
  if (item.can_url) add(str("picker_ctx_url"), () => select(item, "url"));
  if (!item.is_folder)
    add(str("picker_ctx_delete"), async () => { await api().remove_item(item.id); refresh(); }, true);
  ctx.classList.remove("hidden");
  const x = Math.min(e.clientX, window.innerWidth - 160);
  const y = Math.min(e.clientY, window.innerHeight - ctx.offsetHeight - 8);
  ctx.style.left = x + "px";
  ctx.style.top = y + "px";
}
function hideCtx() { $("#ctx").classList.add("hidden"); }

/* ---------- 등록 모달 ---------- */
function openAdd() {
  $("#add-error").classList.add("hidden");
  $("#add-url").value = "";
  $("#add-name").value = "";
  $("#add-kw").value = "";
  $("#modal-add").classList.remove("hidden");
  $("#add-url").focus();
}
async function submitAdd() {
  const url = $("#add-url").value.trim();
  if (!url || !api()) return;
  const res = await api().register_url(url, $("#add-name").value.trim(), $("#add-kw").value.trim());
  if (res.ok) { $("#modal-add").classList.add("hidden"); refresh(); }
  else {
    const el = $("#add-error");
    el.textContent = str("picker_err_" + res.error);
    el.classList.remove("hidden");
  }
}

/* ---------- 폴더 설정 ---------- */
function renderFolders() {
  const box = $("#st-folders");
  box.innerHTML = "";
  for (const f of state.folders) {
    const row = document.createElement("div");
    row.className = "folder-row" + (f.exists ? "" : " missing");
    const span = document.createElement("span");
    span.textContent = f.path + " (" + str("picker_tab_" + f.default_type) + ")";
    span.title = f.path;
    const del = document.createElement("button");
    del.textContent = "✕";
    del.addEventListener("click", async () => { await api().remove_folder(f.path); refresh(); });
    row.appendChild(span);
    row.appendChild(del);
    box.appendChild(row);
  }
}

/* ---------- 이벤트 배선 ---------- */
$("#search").addEventListener("input", (e) => { state.query = e.target.value; render(); });
$("#search").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { const first = filtered()[0]; if (first) select(first, "file"); }
});
document.querySelectorAll(".tab").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    b.classList.add("active");
    state.tab = b.dataset.tab;
    render();
  }));
$("#btn-add").addEventListener("click", openAdd);
$("#add-submit").addEventListener("click", submitAdd);
$("#add-url").addEventListener("keydown", (e) => { if (e.key === "Enter") submitAdd(); });
$("#add-cancel").addEventListener("click", () => $("#modal-add").classList.add("hidden"));
$("#btn-settings").addEventListener("click", () => $("#modal-settings").classList.remove("hidden"));
$("#st-close").addEventListener("click", () => $("#modal-settings").classList.add("hidden"));
$("#st-addfolder").addEventListener("click", async () => {
  if (api()) { await api().add_folder(state.tab); refresh(); }
});

document.addEventListener("click", (e) => { if (!$("#ctx").contains(e.target)) hideCtx(); });
window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const open = [$("#modal-add"), $("#modal-settings")].find((m) => !m.classList.contains("hidden"));
  if (open) { open.classList.add("hidden"); return; }
  if (!$("#ctx").classList.contains("hidden")) { hideCtx(); return; }
  if (api()) api().hide();
});
window.addEventListener("blur", () => { if (api()) api().hide(); });

/* ---------- 드래그앤드롭 (pywebviewFullPath) ---------- */
let dragDepth = 0;
window.addEventListener("dragenter", (e) => { e.preventDefault(); dragDepth++; $("#dropzone").classList.remove("hidden"); });
window.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#dropzone").classList.add("hidden"); } });
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", async (e) => {
  e.preventDefault();
  dragDepth = 0;
  $("#dropzone").classList.add("hidden");
  if (!api()) return;
  const paths = [...e.dataTransfer.files].map((f) => f.pywebviewFullPath).filter(Boolean);
  if (paths.length) { await api().register_files(paths, state.tab); refresh(); }
});

/* ---------- 클립보드 이미지 붙여넣기 등록 (스펙 §5) ---------- */
let hintTimer = 0;
function flashHint(key) {
  const f = $("#hint");
  f.textContent = str(key);
  clearTimeout(hintTimer);
  hintTimer = setTimeout(() => { f.textContent = str("picker_hint"); }, 1800);
}
window.addEventListener("paste", async (e) => {
  /* 등록 모달이 열려 있으면 URL 등 네이티브 붙여넣기를 방해하지 않는다 */
  if (!$("#modal-add").classList.contains("hidden")) return;
  if (!api()) return;
  /* 이미지가 있을 때만 가로챈다 — 텍스트 붙여넣기는 검색창 네이티브 동작에 맡긴다.
     실제 원본 PNG 바이트는 Python이 클립보드에서 직접 읽는다(재인코딩 방지). */
  const items = (e.clipboardData && e.clipboardData.items) || [];
  const hasImage = [...items].some((it) => it.type && it.type.indexOf("image/") === 0);
  if (!hasImage) return;
  e.preventDefault();
  const res = await api().register_clipboard(state.tab);
  if (res && res.ok) refresh();
  else flashHint("picker_paste_no_image");
});

/* ---------- 표시 훅 (Python이 호출) ---------- */
window.__onShow = () => {
  state.query = "";
  $("#search").value = "";
  hideCtx();
  refresh();
  setTimeout(() => $("#search").focus(), 30);
};

if (window.pywebview) refresh();
else window.addEventListener("pywebviewready", refresh);
setTimeout(() => { if (!window.pywebview) refresh(); }, 60); /* 브라우저 mock */
