from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.http_json import HttpJsonTransportError, request_json  # noqa: E402


class HttpJsonTest(unittest.TestCase):
    def test_transport_errors_have_a_shared_exception_type(self) -> None:
        with mock.patch("scripts.http_json.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(HttpJsonTransportError):
                request_json("https://example.test")

    def test_read_timeout_has_a_shared_exception_type(self) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = TimeoutError("timed out")
        with mock.patch("scripts.http_json.urlopen", return_value=response):
            with self.assertRaises(HttpJsonTransportError):
                request_json("https://example.test")

    def test_json_body_and_response_are_normalized(self) -> None:
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = b'{"data": {"ok": true}}'
        response.__enter__.return_value = response
        with mock.patch("scripts.http_json.urlopen", return_value=response) as opener:
            result = request_json(
                "https://example.test",
                method="POST",
                headers={"Accept": "application/json"},
                json_body={"query": "ok"},
            )
        self.assertEqual(result, {"status": 200, "json": {"data": {"ok": True}}})
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")


if __name__ == "__main__":
    unittest.main()
