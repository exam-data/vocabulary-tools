/* 词汇工具箱：浏览器本地执行，无服务器 */
const REMOTE = {
  netem: "https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json",
  cet: "https://raw.githubusercontent.com/exam-data/CETVocabulary/main/cet_full_list.json",
  netem_beyond: "https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_beyond_ks3000.json",
  cet_beyond: "https://raw.githubusercontent.com/exam-data/CETVocabulary/main/cet_beyond_ks3000.json",
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
  if (slot === "docx") fillColPicker();
}

// 选择本地文件后同样列出可选列
document.getElementById("docx-file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  try {
    loaded.docx = { name: f.name, json: JSON.parse(await f.text()) };
    fillColPicker();
    log(`已读取 ${f.name}`);
  } catch (err) { log("JSON 解析失败：" + err.message); }
});

function fillColPicker() {
  const src = loaded.docx;
  if (!src) return;
  let rows;
  try { [, rows] = tableOf(src.json); } catch (e) { log(e.message); return; }
  const picker = document.getElementById("col-picker");
  const DEFAULT_COLS = ["序号", "词频", "单词", "释义"];
  picker.innerHTML = Object.keys(rows[0]).map((f) =>
    `<label class="col-pill"><input type="checkbox" value="${f}"${DEFAULT_COLS.includes(f) ? " checked" : ""}>${f}</label>`).join("");
}
function pickCols(on) {
  document.querySelectorAll("#col-picker input[type=checkbox]").forEach((c) => (c.checked = on));
}
function checkedCols() {
  return [...document.querySelectorAll("#col-picker input:checked")].map((c) => c.value);
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

/* ---------- ① JSON → docx（内建美化：等效 tools/macro.js） ---------- */
const DOCX_STYLE = {
  headerFill: "808080",          // 首行灰底（wdColorGray50）
  border: { style: "single", size: 4, color: "000000" },  // 0.5pt 黑边
  rowHeight: 624,                // 31.18pt ≈ 1.1cm（行高至少）
  font: "华文中宋",
};
const PAGE_TEXT_TWIPS = 9026;    // A4 竖版 - 默认左右页边距 1"
const CELL_MARGIN_TWIPS = 216;   // 单元格左右内边距
const FONT_SIZE_PT = 11;
const CHAR_TWIPS = FONT_SIZE_PT * 20;
const LATIN_TW = 122;              // 11pt 拉丁字符约 6.1pt = 122 twips
function computeWidths(fields, rows) {
  // 内容自适应：按各列真实内容最大长度定宽（保证单行）；释义为弹性列；超页宽则等比收缩
  const latinW = (v) => String(v).length * LATIN_TW + CELL_MARGIN_TWIPS;
  const cjkW = (v) => String(v).length * 220 + CELL_MARGIN_TWIPS;
  const widths = fields.map(f => {
    if (f === "释义") return null;
    if (f === "六级") return 700;  // 表头「六级」+星号单行
    if (["序号", "原序号", "词频", "综合得分"].includes(f))
      return Math.min(Math.max(...rows.filter(r => r[f] != null).map(r => latinW(r[f])), 500), 1000);
    if (f === "单词")
      return Math.min(Math.max(...rows.map(r => latinW(r["单词"])), 800), 2400);
    if (f === "其他拼写") {
      const m = Math.max(...rows.filter(r => r[f]).map(r => latinW(r[f])), 0);
      return Math.min(Math.max(m || 600, 800), 1700);
    }
    if (f === "分类名称") return 1600;   // 竖版宽度有限，长分类名自动折行
    if (f === "CEFR等级") return 1150;
    if (["学术词汇", "高级词汇"].includes(f)) return 900;
    return 1100;
  });
  const fixed = widths.reduce((s, w) => s + (w || 0), 0);
  const flex = PAGE_TEXT_TWIPS - fixed;
  if (flex < 1400)
    throw new Error(`列太多：固定列已占 ${fixed}，释义列不足 1400 twips，超出 A4 宽度，不能生成（请减少勾选列）`);
  return widths.map(w => w === null ? flex : w);
}
function breakDef(s, maxLen, seps = "、；") {
  s = s.trim();
  if (!s) return s;
  const parts = s.split(new RegExp("([" + seps + "])"));
  const items = [];
  for (let i = 0; i < parts.length; i += 2) {
    const word = parts[i], sep = parts[i + 1] || "";
    if (word) items.push(word + sep);
  }
  const lines = []; let cur = [], curlen = 0;
  for (const item of items) {
    if (cur.length && curlen + item.length > maxLen) { lines.push(cur.join("")); cur = []; curlen = 0; }
    cur.push(item); curlen += item.length;
    if (item.length > maxLen) { lines.push(cur.join("")); cur = []; curlen = 0; }
  }
  if (cur.length) lines.push(cur.join(""));
  return lines.map(l => l.replace(/[、；]$/, "")).join("\n");
}
async function runDocx() {
  try {
    const src = await getJson("docx", "docx-file");
    if (!src) return;
    const [, rows] = tableOf(src.json);
    let fields = checkedCols();
    if (!fields.length) { log("请至少勾选一列"); return; }
    const bad = fields.filter((f) => !(f in rows[0]));
    if (bad.length) { log(`字段不存在：${bad.join("、")}（数据换过了？重新勾选）`); return; }
    const perPage = Math.max(1, parseInt(document.getElementById("per-page").value) || 18);
    let widths;
    try { widths = computeWidths(fields, rows); }
    catch (e) { log("出错：" + e.message); return; }
    const defIdx = fields.indexOf("释义");
    const maxLen = defIdx >= 0 ? Math.max(1, Math.floor((widths[defIdx] - CELL_MARGIN_TWIPS) / CHAR_TWIPS)) : 0;
    if (defIdx >= 0) log(`释义列宽 ${widths[defIdx]} twips → 单行最大 ${maxLen} 字（随勾选列数联动），超长释义按顿号/分号断行`);
    const { Document, Packer, Paragraph, Table, TableRow, TableCell, TextRun, WidthType,
            PageBreak, AlignmentType, VerticalAlign, HeightRule, BorderStyle, TableLayoutType } = docx;
    const B = { style: BorderStyle.SINGLE, size: DOCX_STYLE.border.size, color: DOCX_STYLE.border.color };
    const borders = { top: B, left: B, bottom: B, right: B, insideHorizontal: B, insideVertical: B };

    const cell = (text, header = false) =>
      new TableCell({
        shading: header ? { fill: DOCX_STYLE.headerFill } : undefined,
        verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 0, line: 240 },
          children: [new TextRun({ text: String(text ?? ""), bold: header, font: DOCX_STYLE.font, size: FONT_SIZE_PT * 2 })],
        })],
      });

    const children = [];
    let idx = 0;
    while (idx < rows.length) {
      const trows = [new TableRow({
        children: fields.map((f) => cell(f, true)),
        tableHeader: true,
        height: { value: DOCX_STYLE.rowHeight, rule: HeightRule.ATLEAST },
      })];
      for (let i = 0; i < perPage && idx < rows.length; i++, idx++) {
        trows.push(new TableRow({
          children: fields.map((f) => {
            let v = rows[idx][f] ?? "";
            if (defIdx >= 0 && f === "释义" && v) v = breakDef(String(v), maxLen);
            return cell(v);
          }),
          height: { value: DOCX_STYLE.rowHeight, rule: HeightRule.ATLEAST },
        }));
      }
      children.push(new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, borders, rows: trows,
        columnWidths: widths, layout: TableLayoutType.FIXED }));
      if (idx < rows.length) children.push(new Paragraph({ pageBreakBefore: true,
        spacing: { before: 0, after: 0 }, children: [] }));   // 换页段落落在下页开头，不产生空白页
    }
    const doc = new Document({
      styles: { default: { document: { run: { font: DOCX_STYLE.font } } } },
      sections: [{ children }],   // A4 竖版默认
    });
    const blob = await Packer.toBlob(doc);
    download(blob, src.name.replace(/\.json$/i, "") + ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    log(`生成完成：${rows.length} 词，每页 ${perPage} 词。已内建美化（首行灰底/边框/居中/行高），打开即是成品。`);
  } catch (e) { log("出错：" + e.message); }
}

/* ---------- ② JSON → SQL ---------- */
const FIELD_MAP = {
  "序号": ["id", "int"], "词频": ["frequency", "int"], "六级": ["cet6", "varchar(32)"],
  "单词": ["word", "varchar(255)"], "释义": ["definition", "varchar(255)"],
  "其他拼写": ["variant", "varchar(255)"], "分类名称": ["category", "varchar(255)"],
  "原序号": ["orig_id", "int"], "CEFR等级": ["cefr", "varchar(8)"],
  "学术词汇": ["nawl", "tinyint(1)"], "高级词汇": ["c1c2", "tinyint(1)"], "综合得分": ["score", "float"],
  "例句": ["sentence", "varchar(512)"], "例句翻译": ["sentence_cn", "varchar(512)"], "例句来源": ["sentence_src", "varchar(255)"],
  "真题次数": ["exam_count", "int"],
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
  orig_id: "原序号", cefr: "CEFR等级", nawl: "学术词汇", c1c2: "高级词汇", score: "综合得分",
  sentence: "例句", sentence_cn: "例句翻译", sentence_src: "例句来源", exam_count: "真题次数" };
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
        row[key] = v === "NULL" ? null : (["id", "frequency", "orig_id", "exam_count"].includes(c) ? parseInt(v)
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
