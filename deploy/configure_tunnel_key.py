"""Store an OpenAI runtime key privately on the container and start its tunnel."""

from getpass import getpass
import os
from pathlib import Path
import re
import subprocess


def main() -> None:
    directory = Path.home() / ".config/tunnel-client"
    path = directory / "runtime.env"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    if not path.exists():
        key = getpass("OpenAI runtime API key (hidden; Enter to cancel): ").strip()
        if not key:
            print("Cancelled.")
            return
        if not re.fullmatch(r"sk-[A-Za-z0-9_-]{10,}", key):
            print("Invalid key format. Paste only the OpenAI runtime API key.")
            return
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"CONTROL_PLANE_API_KEY={key}\n")
        del key
        print("Key saved privately outside the repository.")
    else:
        print("Using the existing private key file.")
    subprocess.run(["systemctl", "--user", "start", "poly-moodle-tunnel.service"], check=True)
    print("Tunnel service started. Check its readiness after a few seconds:")
    print("curl --fail http://127.0.0.1:8080/readyz")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
