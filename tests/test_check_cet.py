import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import check_cet


class CheckCETTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data/sql").mkdir(parents=True)
        full = [
            {"序号": 1, "词频": 100, "六级": None, "单词": "one", "英式音标": "/wʌn/", "释义": "一", "例句": "One example.", "例句翻译": "一个例子。", "例句来源": "无"},
            {"序号": 2, "词频": 10, "六级": "★", "单词": "two", "英式音标": "/tuː/", "释义": "二", "例句": "Two examples.", "例句翻译": "两个例子。", "例句来源": "语料"},
        ]
        ranked = []
        for i, row in enumerate(reversed(full), 1):
            ranked.append({"序号": i, "原序号": row["序号"], **{k: v for k, v in row.items() if k != "序号"}})
        beyond = [{"序号": 1, "原序号": 2, **{k: v for k, v in full[1].items() if k != "序号"}}]
        self.rows = {"full": full, "reranked": ranked, "beyond": beyond, "beyond-reranked": copy.deepcopy(beyond)}
        names = {"full": "cet_full_list", "reranked": "cet_reranked", "beyond": "cet_beyond_ks3000", "beyond-reranked": "cet_beyond_ks3000_reranked"}
        self.items = [{"id": ident, "count": len(rows), "json": names[ident] + ".json", "sql": "data/sql/" + names[ident] + ".sql", "table": names[ident], "list_key": "词汇表"} for ident, rows in self.rows.items()]
        self.save_catalog()
        for ident in self.rows:
            self.save_dataset(ident)

    def tearDown(self):
        self.temp.cleanup()

    def save_catalog(self):
        (self.root / "data/catalog.json").write_text(json.dumps({"datasets": self.items}, ensure_ascii=False))

    def save_dataset(self, ident):
        ds = next(d for d in self.items if d["id"] == ident)
        path = self.root / ds["json"]
        path.write_text(json.dumps({"词汇表": self.rows[ident]}, ensure_ascii=False))
        subprocess.run([sys.executable, str(TOOLS / "json_to_sql.py"), str(path), "-o", str(self.root / ds["sql"])], check=True, capture_output=True)

    def test_four_versions_validate(self):
        result = check_cet.check(self.root)
        self.assertEqual(set(result), check_cet.EXPECTED)

    def test_sql_definition_mismatch_is_detected(self):
        ds = self.items[0]
        sql = self.root / ds["sql"]
        sql.write_text(sql.read_text().replace("'一'", "'篡改'"))
        with self.assertRaisesRegex(ValueError, "SQL 逐行字段"):
            check_cet.check(self.root)

    def test_wrong_original_id_is_detected_even_if_sql_is_synced(self):
        self.rows["reranked"][0]["原序号"] = 1
        self.save_dataset("reranked")
        with self.assertRaisesRegex(ValueError, "原序号不符"):
            check_cet.check(self.root)

    def test_cross_version_nonexample_field_mismatch_is_detected(self):
        self.rows["beyond"][0]["六级"] = None
        self.save_dataset("beyond")
        with self.assertRaisesRegex(ValueError, "字段与主表不一致"):
            check_cet.check(self.root)

    def test_catalog_path_escape_is_rejected(self):
        self.items[0]["json"] = "../outside.json"
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "路径越界"):
            check_cet.check(self.root)

    def test_unknown_core_or_compatibility_entry_is_rejected(self):
        self.items[-1]["id"] = "core"
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "不设核心或兼容版"):
            check_cet.check(self.root)


if __name__ == "__main__":
    unittest.main()
