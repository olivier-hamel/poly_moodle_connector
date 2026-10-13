# Poly Moodle MCP

A personal, read-only MCP server for a Polytechnique Montreal
Moodle account. List enrolled courses, browse course attachments, and extract
text from PDF, DOCX, PPTX, TXT, Markdown, CSV, JSON, and HTML files.

## Requirements

- Python 3.11 or later.
- An Moodle account with access to the required web services.
- Node.js for the optional MCP Inspector.

## Install

From the project directory:

```bash
python -m venv .venv
```

Windows Git Bash:

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

In the examples below, `python` means the interpreter in this virtual
environment. Activate it with `source .venv/Scripts/activate` in Windows Git Bash
or `source .venv/bin/activate` on Linux.

## Authenticate through your browser

```bash
python setup_browser_access.py
```

The script prints a URL; it does not open the browser automatically.

1. Open Developer Tools with F12 and select **Network**.
2. Enable **Persist Logs** so redirects remain visible.
3. Copy the URL printed by the running script into that browser tab.
4. Log in normally if prompted. Browser may say the address was not understood
   because no app is registered for the `moodlemobile://` scheme.
5. Select the final `launch.php` request with HTTP status **302**.
6. Under **Headers > Response headers**, copy the complete **Location** value,
   starting with `moodlemobile://token=`. Include any trailing `==`.
7. Paste only that value into the script's hidden terminal prompt and press
   Enter. In Git Bash, use Shift+Insert or right-click > Paste. Characters are
   intentionally invisible.
8. After **API authentication: SUCCESS**, enter `y` to save the local token.

The script validates that the redirect matches the site and the current login
attempt, then checks the token against Moodle. A bad paste can be retried without
restarting. If you restart, use the newly printed URL and its new redirect.
An empty input cancels. Existing token files are never overwritten.

The token is stored beside the scripts in `.moodle_token`. Alternatively, the
server reads a `MOODLE_TOKEN` environment variable, which takes precedence.
An RSS key is not a web-service token.

Browser authentication depends on the Moodle site's mobile-login configuration.
If it returns a Moodle configuration or permission error, this method may not
be enabled for your account/site.

### Alternative: password login

```bash
python setup_access.py
```

This posts your locally entered credentials to `/login/token.php`. Some sites
challenge this request through a security gateway; HTTP 202 with HTML is not a
Moodle JSON token response. Use browser authentication in that case.

### Connection diagnostic

```bash
python diagnose_connection.py
```

This checks the token and REST endpoints without credentials or session cookies.
An `invalidtoken` JSON error from REST is expected. An AWS WAF `challenge` header
identifies a browser challenge. Response bodies and cookies are not printed.

## Test the MCP tools

From the project directory, 

```bash
npx @modelcontextprotocol/inspector .venv/bin/python server.py
```

Keep the terminal running, open the Inspector URL it prints, and connect using
**STDIO**. In **Tools**, call:

| Tool | Inputs | Result |
| --- | --- | --- |
| `list_courses` | None | Enrolled courses and their IDs |
| `list_files` | `course_id` from `list_courses` | Attachments and their IDs |
| `read_file` | Same `course_id`, plus a file's `id` as `file_id` | Extracted text |

The Inspector launches the server itself. Running `python server.py` directly
starts a stdio server that waits for an MCP client; silence is normal.

Offline regression checks:

```bash
python -m unittest discover -s tests -v
```

## Limits

- No submissions, grades, or other Moodle write operations.
- Downloads limited to 25 MB; returned text limited to 50,000 characters.
- API and download redirects are refused.
- Downloads accept only HTTPS pluginfile URLs on the configured Moodle origin.
- Scanned PDFs require OCR, which is not included.
- Unsupported formats, videos, H5P, and externally hosted resources are not read.
- A mobile token can have broader permissions than the tools exposed here.
- This server uses one account; it is not a multi-user service.
- Tokens can expire or be revoked. Remove your local token file and rerun setup
  when replacing one; also clear `MOODLE_TOKEN` if it is set.

## Project files

| File | Purpose |
| --- | --- |
| `server.py` | Three read-only MCP tools |
| `moodle_client.py` | Moodle API calls, downloads, and text extraction |
| `setup_browser_access.py` | Browser mobile-login token import |
| `setup_access.py` | Optional direct password login |
| `access_setup.py` | Shared token validation and storage |
| `diagnose_connection.py` | Credential-free endpoint checks |
| `tests/test_security.py` | Offline security regression checks |

References: [Moodle mobile login implementation](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/admin/tool/mobile/launch.php),
[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector),
[OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
