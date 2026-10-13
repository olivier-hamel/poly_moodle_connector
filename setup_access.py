"""Run once on your own computer to request a Moodle token securely.

Never paste a token or password into ChatGPT, email, or source control.
"""

from getpass import getpass
import requests
from access_setup import validate_and_store
from moodle_client import BASE_URL, TOKEN_FILE


def main() -> None:
    if TOKEN_FILE.exists():
        print("A local token file already exists; it has not been replaced.")
        return
    print("Poly Moodle: authorized, read-only API setup")
    username = input("Moodle username: ").strip()
    password = getpass("Moodle password (hidden): ")
    try:
        response = requests.post(
            f"{BASE_URL}/login/token.php",
            data={"username": username, "password": password,
                  "service": "moodle_mobile_app"},
            timeout=30,
            allow_redirects=False,
        )
    except requests.exceptions.SSLError:
        print("Network error: SSLError (TLS/certificate verification).")
        return
    except requests.exceptions.ProxyError:
        print("Network error: ProxyError (network proxy).")
        return
    except requests.exceptions.Timeout:
        print("Network error: Timeout (no response within 30 seconds).")
        return
    except requests.exceptions.ConnectionError:
        print("Network error: ConnectionError (network/DNS/connection).")
        return
    except requests.RequestException as exc:
        print("Network error:", type(exc).__name__)
        return
    finally:
        del password

    print("Token endpoint HTTP status:", response.status_code)
    print("Response content type:", response.headers.get("Content-Type", "not provided"))
    if 300 <= response.status_code < 400:
        print("Token request redirected; refusing to follow authentication redirects.")
        return
    try:
        result = response.json()
    except ValueError:
        print("Non-JSON response: an HTML challenge, maintenance page, or server error is possible.")
        print("No server content has been displayed.")
        print("Try browser login instead: python setup_browser_access.py")
        return
    if not 200 <= response.status_code < 300:
        code = result.get("errorcode", "not provided") if isinstance(result, dict) else "not provided"
        print("HTTP error; Moodle error code:", code)
        return

    token = result.get("token") if isinstance(result, dict) else None
    if not token:
        print("Token not issued. Moodle error code:",
              result.get("errorcode", "unknown") if isinstance(result, dict) else "unknown")
        return
    validate_and_store(token)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
