"""Shared validation and local storage for interactive setup commands."""

import os

from moodle_client import MoodleClient, MoodleError, TOKEN_FILE


def validate_and_store(token: str) -> bool:
    """Validate a token without printing it, then ask before storing it."""
    try:
        info = MoodleClient(token).site_info()
    except MoodleError as exc:
        print("API validation failed:", exc)
        return False
    if not isinstance(info, dict) or "userid" not in info:
        print("API validation failed: Moodle did not return a user ID.")
        return False
    allowed = {f.get("name") for f in info.get("functions", []) if isinstance(f, dict)}
    print("API authentication: SUCCESS")
    for function in ("core_enrol_get_users_courses", "core_course_get_contents"):
        print(f"{function}: {'available' if function in allowed else 'not listed'}")
    if input("Store the token locally for the MCP server? [y/N]: ").strip().lower() != "y":
        print("Token discarded.")
        return False
    try:
        # Exclusive creation also refuses pre-existing links.
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
        os.chmod(TOKEN_FILE, 0o600)
    except FileExistsError:
        print("A local token file already exists; it has not been replaced.")
        return False
    except OSError:
        print("Could not store the token. Check the file and directory permissions.")
        return False
    print("Saved local token file. Next: python server.py")
    return True
