import tempfile
import unittest
from pathlib import Path

from tests import context  # noqa: F401
from quant_trading.research_log import ResearchStep, append_research_log, steps_to_dicts


class ResearchLogTests(unittest.TestCase):
    def test_append_research_log_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research_log.jsonl"

            append_research_log(path, "screener", {"strategy": "momentum", "candidate_count": 2})

            content = path.read_text(encoding="utf-8")
            self.assertIn('"run_type": "screener"', content)
            self.assertIn('"candidate_count": 2', content)

    def test_steps_to_dicts(self):
        rows = steps_to_dicts([ResearchStep("行情", "ok", "完成")])

        self.assertEqual(rows[0]["stage"], "行情")


if __name__ == "__main__":
    unittest.main()
