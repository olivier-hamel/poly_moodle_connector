# Poly Moodle MCP

A personal, read-only MCP server for a Polytechnique Montreal
Moodle account. List enrolled courses, calendar events and assignment deadlines,
browse course attachments, and extract
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
| `list_events` | Optional `course_id`, `time_start`, `time_end` | Calendar events, sorted by date; defaults to the next 90 days |
| `list_assignments` | Optional `course_id`, `include_personal_deadlines` | Submission boxes, due dates, opening/closing dates, personal extensions and submission status |
| `list_files` | `course_id` from `list_courses` | Attachments and their IDs |
| `read_file` | Same `course_id`, plus a file's `id` as `file_id` | Extracted text |

The Inspector launches the server itself. Running `python server.py` directly
starts a stdio server that waits for an MCP client; silence is normal.

### Calendar and submission deadlines

Omit `course_id` to query all your courses. For `list_events`, the optional time
bounds are Unix timestamps in seconds. Personal, site and category events are
included when querying all courses; a course filter returns only that course's
events, including events for your groups.

`list_assignments` includes past assignments and boxes with no deadline. `due_at`
is the assignment due date returned by Moodle (including applicable overrides);
`cutoff_at` is the date submissions close, which may differ from the due date.
By default, an additional read per submission box checks your extension and
submission status. Use `effective_due_at` when `personal_deadline_checked` is
true. If verification fails, this date stays null and a warning is returned;
the unverified `due_at` remains available. Set `include_personal_deadlines=false`
for a faster list without checking extensions or status.

Dates are ISO 8601 in UTC with an explicit `+00:00` offset. Convert to
`America/Toronto` for Montreal local time, including daylight saving changes.
Unset dates are null. Inspect `warnings` before treating results as complete.
These tools support Moodle `assign` submission boxes; other activities such as
quizzes may have dates in the calendar but are not assignment boxes.

The token's web service must permit `core_calendar_get_calendar_events`,
`core_group_get_course_user_groups`, `mod_assign_get_assignments`, and (for
personal extensions) `mod_assign_get_submission_status`. An API permission error
needs a Moodle administrator or a token/service with those functions enabled.

After copying the updated `moodle_client.py`, `server.py` and
`deploy/check_server.py` to an existing deployment, restart the service:

```bash
systemctl --user restart poly-moodle.service
~/poly-moodle/.venv/bin/python ~/poly-moodle/deploy/check_server.py
```

Reconnect or refresh the MCP connector's tools in your client if it still shows
the old tool list. The existing service unit requires no change.

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
| `server.py` | Five read-only MCP tools |
| `moodle_client.py` | Moodle API calls, downloads, and text extraction |
| `setup_browser_access.py` | Browser mobile-login token import |
| `setup_access.py` | Optional direct password login |
| `access_setup.py` | Shared token validation and storage |
| `diagnose_connection.py` | Credential-free endpoint checks |
| `tests/test_security.py` | Offline security regression checks |
| `tests/test_calendar.py` | Calendar, deadline and MCP discovery checks |

References: [Moodle mobile login implementation](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/admin/tool/mobile/launch.php),
[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector),
[OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
