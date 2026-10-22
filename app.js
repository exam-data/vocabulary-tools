/* 数据浏览器：纯静态，直接拉取两个数据仓 master 分支的 JSON */
const DATASETS = {
  netem: {
    url: "https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json",
    label: "考研",
    hasCet6: false,
  },
  cet: {
    url: "https://raw.githubusercontent.com/exam-data/CETVocabulary/master/cet_full_list.json",
    label: "四六级",
    hasCet6: true,
  },
};

const PAGE = 200;
const state = {
  ds: "netem",
  data: { netem: null, cet: null },
  filtered: [],
  shown: 0,
  search: "",
  category: "",
  sort: "id",
  cet6only: false,
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
  const rows = json[Object.keys(json)[0]];
  state.data[ds] = rows;
  return rows;
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
  const chunk = state.filtered.slice(state.shown, state.shown + PAGE);
  const cet = DATASETS[state.ds].hasCet6;
  const html = chunk.map((r) => `
    <tr>
      <td class="num">${r["序号"]}</td>
      <td class="word">${esc(r["单词"])}${cet && r["六级"] ? '<span class="cet6">★</span>' : ""}</td>
      <td class="def">${esc(r["释义"])}</td>
      <td class="cat">${esc(r["分类名称"] || "")}</td>
      <td class="variant">${esc(r["其他拼写"] || "")}</td>
      <td class="num">${r["词频"] ?? ""}</td>
    </tr>`).join("");
  tbody.insertAdjacentHTML("beforeend", html);
  state.shown += chunk.length;
  sentinel.textContent = state.shown < state.filtered.length ? "向下滚动加载更多…" : "到底啦";
}

function renderHead() {
  $("#grid thead").innerHTML = `<tr>
    <th>#</th><th>单词</th><th>释义</th><th>分类</th><th>其他拼写</th><th>词频</th>
  </tr>`;
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

// 事件绑定
document.querySelectorAll(".ds-btn").forEach((b) =>
  b.addEventListener("click", () => switchDataset(b.dataset.ds)));
$("#search").addEventListener("input", (e) => { state.search = e.target.value; applyFilter(); });
$("#category").addEventListener("change", (e) => { state.category = e.target.value; applyFilter(); });
$("#sort").addEventListener("change", (e) => { state.sort = e.target.value; applyFilter(); });
$("#cet6").addEventListener("change", (e) => { state.cet6only = e.target.checked; applyFilter(); });

// 滚动到底自动加载
new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting && state.shown < state.filtered.length) renderMore();
}).observe(sentinel);

switchDataset("netem");
