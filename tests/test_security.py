"""Offline checks for login binding, token storage, and redirect protection."""

import base64
from contextlib import redirect_stdout
import hashlib
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from access_setup import validate_and_store
from moodle_client import BASE_URL, MoodleClient, MoodleError
from setup_browser_access import decode_redirect


class SecurityTests(unittest.TestCase):
    def test_browser_redirect_is_bound_to_site_and_login(self):
        passport = "test-login"
        token = "a" * 32
        site = hashlib.md5((BASE_URL + passport).encode()).hexdigest()
        encoded = base64.b64encode(f"{site}:::{token}:::private".encode()).decode()
        redirect = "moodlemobile://token=" + encoded
        self.assertEqual(decode_redirect(redirect, passport), token)
        for candidate, nonce in ((redirect, "other-login"),
                                 ("https://example.com", passport),
                                 ("moodlemobile://token=invalid", passport)):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                decode_redirect(candidate, nonce)

    def test_api_refuses_redirects_and_hides_token_in_repr(self):
        client = MoodleClient("secret-test-token")
        self.assertNotIn(client.token, repr(client))
        with patch("moodle_client.requests.post", return_value=Mock(status_code=302)) as post:
            with self.assertRaises(MoodleError):
                client.site_info()
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_setup_does_not_overwrite_or_print_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".moodle_token"
            output = StringIO()
            with patch("access_setup.TOKEN_FILE", path), \
                 patch("access_setup.MoodleClient.site_info", return_value={"userid": 1}), \
                 patch("builtins.input", return_value="y"), redirect_stdout(output):
                self.assertTrue(validate_and_store("first-test-token"))
                self.assertFalse(validate_and_store("second-test-token"))
            self.assertEqual(path.read_text().strip(), "first-test-token")
            self.assertNotIn("first-test-token", output.getvalue())
            self.assertNotIn("second-test-token", output.getvalue())


if __name__ == "__main__":
    unittest.main()
