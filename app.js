/* 数据浏览器：纯静态，直接拉取数据仓 master 分支的 JSON */
const DATASETS = {
  netem: {
    url: "https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json",
    label: "考研·词频序", hasCet6: false,
  },
  netem_reranked: {
    url: "https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_reranked.json",
    label: "考研·智能重排", hasCet6: false, enriched: true,
  },
  cet: {
    url: "https://raw.githubusercontent.com/exam-data/CETVocabulary/master/cet_full_list.json",
    label: "四六级·词频序", hasCet6: true,
  },
  cet_reranked: {
    url: "https://raw.githubusercontent.com/exam-data/CETVocabulary/master/cet_reranked.json",
    label: "四六级·智能重排", hasCet6: true, enriched: true,
  },
};

// 列定义：key -> 表头/取值渲染/是否默认（enriched 数据集才显示）
const COLUMNS = [
  { key: "序号", label: "#", cls: "num", get: (r) => r["序号"] },
  { key: "单词", label: "单词", cls: "word", get: (r, cet) => esc(r["单词"]) + (cet && r["六级"] ? '<span class="cet6">★</span>' : ""), raw: true },
  { key: "释义", label: "释义", cls: "def", get: (r) => r["释义"] },
  { key: "分类名称", label: "分类", cls: "cat", get: (r) => r["分类名称"] },
  { key: "CEFR等级", label: "CEFR", cls: "cat", enriched: true, get: (r) => r["CEFR等级"] || "" },
  { key: "学术词汇", label: "学术", cls: "cat", enriched: true, get: (r) => r["学术词汇"] ? "是" : "" },
  { key: "高级词汇", label: "高级", cls: "cat", enriched: true, get: (r) => r["高级词汇"] ? "是" : "" },
  { key: "综合得分", label: "评分", cls: "num", enriched: true, get: (r) => r["综合得分"] ?? "" },
  { key: "其他拼写", label: "其他拼写", cls: "variant", get: (r) => r["其他拼写"] },
  { key: "词频", label: "词频", cls: "num", get: (r) => r["词频"] ?? "" },
];

const PAGE = 200;
const state = {
  ds: "netem", data: {}, filtered: [], shown: 0,
  search: "", category: "", sort: "id", cet6only: false,
};

const $ = (s) => document.querySelector(s);
const tbody = $("#grid tbody");
const sentinel = $("#sentinel");

async function load(ds) {
  if (state.data[ds]) return state.data[ds];
  sentinel.textContent = "数据加载中…";
  const resp = await fetch(DATASETS[ds].url);
  if (!resp.ok) throw new Error(`拉取失败 HTTP ${resp.status}`);
  const json = await resp.json();
  const rows = json[Object.keys(json).find((k) => Array.isArray(json[k]))];
  state.data[ds] = rows;
  return rows;
}

function activeColumns() {
  const enriched = DATASETS[state.ds].enriched;
  return COLUMNS.filter((c) => !c.enriched || enriched);
}

function applyFilter() {
  const rows = state.data[state.ds] || [];
  const q = state.search.trim().toLowerCase();
  let out = rows.filter((r) => {
    if (state.category && r["分类名称"] !== state.category) return false;
    if (state.cet6only && !r["六级"]) return false;
    if (!q) return true;
    return r["单词"].toLowerCase().includes(q) || (r["释义"] || "").includes(q);
  });
  if (state.sort === "freq") out = [...out].sort((a, b) => (b["词频"] || 0) - (a["词频"] || 0));
  else if (state.sort === "alpha") out = [...out].sort((a, b) => a["单词"].localeCompare(b["单词"]));
  state.filtered = out;
  state.shown = 0;
  tbody.innerHTML = "";
  renderMore();
  $("#count").textContent = `共 ${out.length} 词`;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function renderMore() {
  const cet = DATASETS[state.ds].hasCet6;
  const cols = activeColumns();
  const chunk = state.filtered.slice(state.shown, state.shown + PAGE);
  const html = chunk.map((r) => "<tr>" + cols.map((c) =>
    `<td class="${c.cls}">${c.raw ? c.get(r, cet) : esc(c.get(r, cet))}</td>`).join("") + "</tr>").join("");
  tbody.insertAdjacentHTML("beforeend", html);
  state.shown += chunk.length;
  sentinel.textContent = state.shown < state.filtered.length ? "向下滚动加载更多…" : "到底啦";
}

function renderHead() {
  $("#grid thead").innerHTML = "<tr>" + activeColumns().map((c) => `<th>${c.label}</th>`).join("") + "</tr>";
  $("#cet6-wrap").classList.toggle("hidden", !DATASETS[state.ds].hasCet6);
}

function fillCategories() {
  const rows = state.data[state.ds] || [];
  const cats = [...new Set(rows.map((r) => r["分类名称"]).filter(Boolean))];
  $("#category").innerHTML = '<option value="">全部分类</option>' +
    cats.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
}

async function switchDataset(ds) {
  state.ds = ds;
  document.querySelectorAll(".ds-btn").forEach((b) => b.classList.toggle("active", b.dataset.ds === ds));
  try {
    await load(ds);
    renderHead();
    fillCategories();
    applyFilter();
  } catch (e) {
    sentinel.textContent = `加载失败：${e.message}（可检查网络后刷新重试）`;
  }
}

document.querySelectorAll(".ds-btn").forEach((b) =>
  b.addEventListener("click", () => switchDataset(b.dataset.ds)));
$("#search").addEventListener("input", (e) => { state.search = e.target.value; applyFilter(); });
$("#category").addEventListener("change", (e) => { state.category = e.target.value; applyFilter(); });
$("#sort").addEventListener("change", (e) => { state.sort = e.target.value; applyFilter(); });
$("#cet6").addEventListener("change", (e) => { state.cet6only = e.target.checked; applyFilter(); });

new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting && state.shown < state.filtered.length) renderMore();
}).observe(sentinel);

switchDataset("netem");
