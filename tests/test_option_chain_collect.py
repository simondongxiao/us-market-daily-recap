from __future__ import annotations

import importlib.util
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "skill" / "scripts" / "option_chain_collect.py"
SPEC = importlib.util.spec_from_file_location("option_chain_collect", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"data": {"ok": true}}'


class FetchJsonRetryTests(unittest.TestCase):
    def test_retries_transient_url_errors(self) -> None:
        attempts = [
            urllib.error.URLError("temporary eof"),
            urllib.error.URLError("temporary reset"),
            _Response(),
        ]
        with patch.object(MODULE.urllib.request, "urlopen", side_effect=attempts) as urlopen:
            with patch.object(MODULE.time, "sleep") as sleep:
                result = MODULE.fetch_json("https://example.com/options")

        self.assertEqual(result, {"data": {"ok": True}})
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
