"""Import a token from Moodle's normal browser-based mobile login."""

import base64
from getpass import getpass
import hashlib
import re
import secrets
from urllib.parse import urlencode

from access_setup import validate_and_store
from moodle_client import BASE_URL, TOKEN_FILE


def decode_redirect(redirect: str, passport: str) -> str:
    """Validate the login nonce and return only the web-service token."""
    match = re.fullmatch(r"moodlemobile://token=([^\s]+)", redirect.strip())
    if not match:
        raise ValueError("Expected a moodlemobile://token=... redirect.")
    encoded = match.group(1)
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeError):
        raise ValueError("The redirect is not valid base64 text.") from None
    fields = decoded.split(":::")
    # MD5 is part of Moodle's response format, not password hashing.
    expected = hashlib.md5((BASE_URL + passport).encode(), usedforsecurity=False).hexdigest()
    if len(fields) not in (2, 3) or not secrets.compare_digest(fields[0], expected):
        raise ValueError("This redirect does not match this login attempt and site.")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", fields[1]):
        raise ValueError("The redirect does not contain a valid Moodle token.")
    return fields[1]


def main() -> None:
    if TOKEN_FILE.exists():
        print("A local token file already exists; it has not been replaced.")
        return

    passport = secrets.token_hex(16)
    url = BASE_URL + "/admin/tool/mobile/launch.php?" + urlencode({
        "service": "moodle_mobile_app", "passport": passport,
        "urlscheme": "moodlemobile",
    })
    print("Open Firefox Developer Tools (F12), select Network, and enable Persist Logs.")
    print("Copy this URL into that browser tab and log in normally:")
    print(url)
    print("If Firefox says the address was not understood, inspect the launch.php")
    print("request in Network. Copy its Location response header beginning")
    print("moodlemobile://token= (use the final redirect after login).")
    print("Paste it only at the hidden prompt below; do not share it in chat.")

    while True:
        redirect = getpass("Mobile redirect (hidden; Enter to cancel): ")
        if not redirect.strip():
            print("Setup cancelled.")
            return
        try:
            token = decode_redirect(redirect, passport)
        except ValueError as exc:
            print(str(exc))
            print("Copy only the full Location value, including any trailing ==.")
            continue
        finally:
            del redirect
        break
    validate_and_store(token)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
