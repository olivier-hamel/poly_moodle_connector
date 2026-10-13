"""Safe diagnostic: sends no username, password, token, or session cookie."""

import requests


BASE = "https://moodle.polymtl.ca"
CHECKS = [
    (
        "Token endpoint",
        "/login/token.php",
        {"service": "moodle_mobile_app"},
    ),
    (
        "REST endpoint",
        "/webservice/rest/server.php",
        {
            "wsfunction": "core_webservice_get_site_info",
            "moodlewsrestformat": "json",
        },
    ),
]

def main() -> None:
    for label, path, data in CHECKS:
        print(f"\n{label}:")
        try:
            response = requests.post(
                BASE + path,
                data=data,
                timeout=20,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            print("Connection error:", type(exc).__name__)
            continue

        print("HTTP status:", response.status_code)
        print(
            "Content-Type:",
            response.headers.get("Content-Type", "unknown"),
        )
        print("AWS WAF action:", response.headers.get("x-amzn-waf-action", "none"))
        try:
            payload = response.json()
        except ValueError:
            print("Response: Not JSON")
            body = response.text.lower()
            hints = [
                label
                for label, marker in (
                    ("Cloudflare", "cloudflare"),
                    ("Akamai", "akamai"),
                    ("Imperva", "imperva"),
                    ("CAPTCHA", "captcha"),
                    ("JavaScript challenge", "enable javascript"),
                )
                if marker in body
            ]
            print(
                "Possible challenge indicators:",
                ", ".join(hints) if hints else "none detected",
            )
        else:
            print("Response: JSON")
            if isinstance(payload, dict):
                print(
                    "Moodle error code:",
                    payload.get("errorcode", "none"),
                )

    print(
        "\nNo username, password, token, or "
        "session cookie was sent or displayed."
    )


if __name__ == "__main__":
    main()
