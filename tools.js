/* 词汇工具箱：浏览器本地执行，无服务器 */
const REMOTE = {
  netem: "https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json",
  cet: "https://raw.githubusercontent.com/exam-data/CETVocabulary/master/cet_full_list.json",
};
const loaded = { docx: null, j2s: null };  // {name, json}

function log(msg) {
  const el = document.getElementById("log");
  el.textContent += (el.textContent === "就绪。" ? "" : "\n") + msg;
  el.scrollTop = el.scrollHeight;
}
function download(content, name, mime) {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mime || "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
  log(`已下载 ${name}`);
}
function readJsonFile(inputId) {
  const f = document.getElementById(inputId).files[0];
  if (!f) return null;
  return f.text().then((t) => ({ name: f.name, json: JSON.parse(t) }));
}
async function loadRemote(slot, ds) {
  log(`拉取 ${ds} 线上数据…`);
  const resp = await fetch(REMOTE[ds]);
  if (!resp.ok) { log(`失败：HTTP ${resp.status}`); return; }
  loaded[slot] = { name: ds + ".json", json: await resp.json() };
  log(`已载入 ${ds}（无需再选文件）`);
}
async function getJson(slot, inputId) {
  if (loaded[slot]) return loaded[slot];
  const r = await readJsonFile(inputId);
  if (!r) log("请先选择文件或载入线上数据");
  return r;
}
function tableOf(json) {
  for (const k of Object.keys(json)) {
    if (Array.isArray(json[k]) && json[k].length && typeof json[k][0] === "object") return [k, json[k]];
  }
  throw new Error("JSON 顶层没有找到词条列表");
}

/* ---------- ① JSON → docx ---------- */
async function runDocx() {
  try {
    const src = await getJson("docx", "docx-file");
    if (!src) return;
    const [, rows] = tableOf(src.json);
    let fields = Object.keys(rows[0]);
    const colsInput = document.getElementById("docx-cols").value.trim();
    if (colsInput) {
      fields = colsInput.split(",").map((s) => s.trim());
      const bad = fields.filter((f) => !(f in rows[0]));
      if (bad.length) { log(`字段不存在：${bad.join("、")}；可用：${Object.keys(rows[0]).join("、")}`); return; }
    }
    const perPage = Math.max(1, parseInt(document.getElementById("per-page").value) || 18);
    const { Document, Packer, Paragraph, Table, TableRow, TableCell, TextRun, WidthType, PageBreak } = docx;

    const cell = (text, bold = false) =>
      new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: String(text ?? ""), bold })] })] });
    const children = [];
    let idx = 0;
    while (idx < rows.length) {
      const trows = [new TableRow({ children: fields.map((f) => cell(f, true)), tableHeader: true })];
      for (let i = 0; i < perPage && idx < rows.length; i++, idx++) {
        trows.push(new TableRow({ children: fields.map((f) => cell(rows[idx][f] ?? "")) }));
      }
      children.push(new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: trows }));
      if (idx < rows.length) children.push(new Paragraph({ children: [new PageBreak()] }));
    }
    const doc = new Document({ sections: [{ children }] });
    const blob = await Packer.toBlob(doc);
    download(blob, src.name.replace(/\.json$/i, "") + ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    log(`生成完成：${rows.length} 词，每页 ${perPage} 词。WPS 中执行 macro.js 美化。`);
  } catch (e) { log("出错：" + e.message); }
}

/* ---------- ② JSON → SQL ---------- */
const FIELD_MAP = {
  "序号": ["id", "int"], "词频": ["frequency", "int"], "六级": ["cet6", "varchar(32)"],
  "单词": ["word", "varchar(255)"], "释义": ["definition", "varchar(255)"],
  "其他拼写": ["variant", "varchar(255)"], "分类名称": ["category", "varchar(255)"],
  "原序号": ["orig_id", "int"], "CEFR等级": ["cefr", "varchar(8)"],
  "学术词汇": ["nawl", "tinyint(1)"], "高级词汇": ["c1c2", "tinyint(1)"], "综合得分": ["score", "float"],
};
function sqlQuote(v) {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "boolean") return v ? "1" : "0";
  if (typeof v === "number") return String(v);
  return "'" + String(v).replace(/\\/g, "\\\\").replace(/'/g, "\\'") + "'";
}
async function runJson2Sql() {
  try {
    const src = await getJson("j2s", "j2s-file");
    if (!src) return;
    const [key, rows] = tableOf(src.json);
    const fields = Object.keys(rows[0]);
    const unknown = fields.filter((f) => !FIELD_MAP[f]);
    if (unknown.length) { log(`未知字段：${unknown.join("、")}`); return; }
    const table = src.name.replace(/\.json$/i, "");
    const colLines = fields.map((f) => {
      const [col, typ] = FIELD_MAP[f];
      const nn = col === "id" ? "NOT NULL" : "NULL DEFAULT NULL";
      const typed = typ === "int" ? "int(0)" : typ;
      return typ.startsWith("varchar")
        ? `  \`${col}\` ${typed} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin ${nn}`
        : `  \`${col}\` ${typed} ${nn}`;
    });
    if (fields.some((f) => FIELD_MAP[f][0] === "id")) colLines.push("  PRIMARY KEY (`id`) USING BTREE");
    const L = ["SET NAMES utf8mb4;", "SET FOREIGN_KEY_CHECKS = 0;", "",
      `DROP TABLE IF EXISTS \`${table}\`;`,
      `CREATE TABLE \`${table}\`  (\n${colLines.join(",\n")}\n) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE utf8mb4_bin ROW_FORMAT = Dynamic;`, ""];
    for (const r of rows) {
      L.push(`INSERT INTO \`${table}\` VALUES (${fields.map((f) => sqlQuote(r[f])).join(", ")});`, "");
    }
    L.push("SET FOREIGN_KEY_CHECKS = 1;");
    download(L.join("\n"), table + ".sql");
    log(`转换完成：${rows.length} 行。`);
  } catch (e) { log("出错：" + e.message); }
}

/* ---------- ③ SQL → JSON ---------- */
const COLUMN_MAP = { id: "序号", frequency: "词频", cet6: "六级", word: "单词",
  definition: "释义", variant: "其他拼写", category: "分类名称",
  orig_id: "原序号", cefr: "CEFR等级", nawl: "学术词汇", c1c2: "高级词汇", score: "综合得分" };
const TITLE_MAP = { netem_full_list: "5530考研词汇词频排序表", cet_full_list: "四六级词汇词频排序表" };

function splitValues(s) {
  const vals = []; let cur = [], inq = false, i = 0;
  while (i < s.length) {
    const c = s[i];
    if (inq) {
      if (c === "\\" && i + 1 < s.length) { cur.push(s[i + 1]); i += 2; continue; }
      if (c === "'") inq = false; else cur.push(c);
    } else {
      if (c === "'") inq = true;
      else if (c === ",") { vals.push(cur.join("").trim()); cur = []; }
      else cur.push(c);
    }
    i++;
  }
  vals.push(cur.join("").trim());
  return vals;
}
async function runSql2Json() {
  try {
    const f = document.getElementById("s2j-file").files[0];
    if (!f) { log("请先选择 .sql 文件"); return; }
    const text = await f.text();
    const m = text.match(/CREATE TABLE `(\w+)`\s*\(([\s\S]*?)\) ENGINE/);
    if (!m) { log("未找到 CREATE TABLE 语句"); return; }
    const table = m[1];
    const cols = [...m[2].matchAll(/^\s*`(\w+)`/gm)].map((x) => x[1]);
    const rows = [];
    for (const line of text.split("\n")) {
      const t = line.trim();
      if (!t.startsWith("INSERT INTO")) continue;
      const vm = t.match(/VALUES \((.*)\);$/);
      if (!vm) continue;
      const vals = splitValues(vm[1]);
      if (vals.length !== cols.length) { log(`列数与值数不符：${t.slice(0, 80)}…`); return; }
      const row = {};
      cols.forEach((c, i) => {
        const key = COLUMN_MAP[c] || c;
        let v = vals[i];
        row[key] = v === "NULL" ? null : (["id", "frequency", "orig_id"].includes(c) ? parseInt(v)
          : ["nawl", "c1c2"].includes(c) ? v === "1"
          : c === "score" ? parseFloat(v) : v);
      });
      rows.push(row);
    }
    const title = TITLE_MAP[table] || table;
    download(JSON.stringify({ [title]: rows }, null, 2), table + ".json", "application/json;charset=utf-8");
    log(`转换完成：${rows.length} 行。`);
  } catch (e) { log("出错：" + e.message); }
}
