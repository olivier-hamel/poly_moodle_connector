"""Read-only Moodle API client for authorized personal use."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import os
import time
import requests

BASE_URL = "https://moodle.polymtl.ca"
TOKEN_FILE = Path(__file__).with_name(".moodle_token")
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TEXT_CHARS = 50_000


class MoodleError(RuntimeError):
    """Avoid copying secret-bearing responses into errors."""


def load_token() -> str:
    token = os.environ.get("MOODLE_TOKEN", "").strip()
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise MoodleError("No token found. Run: python setup_browser_access.py")
    return token


@dataclass
class MoodleClient:
    token: str = field(repr=False)

    def call(self, function: str, **parameters):
        form = {"wstoken": self.token, "wsfunction": function,
                "moodlewsrestformat": "json", **parameters}
        try:
            response = requests.post(
                f"{BASE_URL}/webservice/rest/server.php",
                data=form, timeout=30, allow_redirects=False,
            )
            if 300 <= response.status_code < 400:
                raise MoodleError("Moodle API redirected; the redirect was not followed.")
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise MoodleError("Moodle API request failed (network or invalid response).") from exc
        if isinstance(data, dict) and data.get("exception"):
            # Do not echo server messages that might contain sensitive details.
            raise MoodleError(f"Moodle API error: {data.get('errorcode', 'unknown')}")
        return data

    def site_info(self):
        return self.call("core_webservice_get_site_info")

    def list_courses(self):
        user_id = self.site_info().get("userid")
        if user_id is None:
            raise MoodleError("Moodle did not return your user ID.")
        courses = self.call("core_enrol_get_users_courses", userid=user_id)
        return [
            {"id": c["id"], "shortname": c.get("shortname", ""),
             "fullname": c.get("fullname", "")}
            for c in courses
        ]

    @staticmethod
    def _date(timestamp):
        """Moodle uses zero for unset dates; expose real dates as UTC ISO 8601."""
        return (datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
                if timestamp else None)

    @staticmethod
    def _warnings(data):
        # Server warning messages can contain traces or private URLs.
        return [{k: warning[k] for k in ("item", "itemid", "warningcode")
                 if k in warning} for warning in data.get("warnings", [])]

    def list_events(self, course_id: int | None = None,
                    time_start: int | None = None, time_end: int | None = None):
        """Read visible calendar events, including current user's group events."""
        if course_id is not None and course_id <= 0:
            raise MoodleError("course_id must be positive.")
        start = int(time.time()) if time_start is None else time_start
        end = start + 90 * 86400 if time_end is None else time_end
        if start < 0 or end <= start:
            raise MoodleError("Use nonnegative Unix timestamps with time_end > time_start.")
        courses = self.list_courses()
        if course_id is not None:
            courses = [course for course in courses if course["id"] == course_id]
            if not courses:
                raise MoodleError("Course not found in your enrolled courses.")
        parameters = {
            "options[timestart]": start, "options[timeend]": end,
            "options[userevents]": int(course_id is None),
            "options[siteevents]": int(course_id is None),
            "options[ignorehidden]": 1,
        }
        for index, course in enumerate(courses):
            parameters[f"events[courseids][{index}]"] = course["id"]
        groups = self.call("core_group_get_course_user_groups", courseid=course_id or 0)
        warnings = self._warnings(groups)
        for index, group in enumerate(groups.get("groups", [])):
            parameters[f"events[groupids][{index}]"] = group["id"]
        data = self.call("core_calendar_get_calendar_events", **parameters)
        warnings.extend(self._warnings(data))
        course_names = {course["id"]: course["shortname"] for course in courses}
        events = []
        for event in data.get("events", []):
            # The legacy API may also return category events for course queries.
            if course_id is not None and event.get("courseid") != course_id:
                continue
            events.append({
                "id": event["id"], "name": event.get("name", ""),
                "course_id": event.get("courseid", 0),
                "course_name": course_names.get(event.get("courseid"), ""),
                "group_id": event.get("groupid", 0),
                "event_type": event.get("eventtype", ""),
                "module": event.get("modulename"),
                "instance_id": event.get("instance"),
                "time_start": event["timestart"],
                "start_at": self._date(event["timestart"]),
                "duration_seconds": event.get("timeduration", 0),
                "url": f"{BASE_URL}/calendar/view.php?view=day&time={event['timestart']}",
            })
        events.sort(key=lambda event: (event["time_start"], event["id"]))
        return {"events": events, "warnings": warnings,
                "time_start": start, "time_end": end, "date_timezone": "UTC"}

    def list_assignments(self, course_id: int | None = None,
                         include_personal_deadlines: bool = True):
        """List assignment dates; optionally verify personal extensions and status."""
        if course_id is not None and course_id <= 0:
            raise MoodleError("course_id must be positive.")
        parameters = {} if course_id is None else {"courseids[0]": course_id}
        data = self.call("mod_assign_get_assignments", **parameters)
        warnings = self._warnings(data)
        assignments = []
        for course in data.get("courses", []):
            for assignment in course.get("assignments", []):
                due = assignment.get("duedate") or 0
                item = {
                    "id": assignment["id"], "module_id": assignment["cmid"],
                    "name": assignment.get("name", ""), "course_id": course["id"],
                    "course_name": course.get("shortname", ""),
                    "due_at": self._date(due),
                    "opens_at": self._date(assignment.get("allowsubmissionsfromdate", 0)),
                    "cutoff_at": self._date(assignment.get("cutoffdate", 0)),
                    "extension_due_at": None, "effective_due_at": None,
                    "personal_deadline_checked": False, "submission_status": None,
                    "submissions_enabled": not bool(assignment.get("nosubmissions", 0)),
                    "url": f"{BASE_URL}/mod/assign/view.php?id={assignment['cmid']}",
                }
                if include_personal_deadlines and item["submissions_enabled"]:
                    try:
                        status = self.call("mod_assign_get_submission_status",
                                           assignid=assignment["id"])
                    except MoodleError:
                        warnings.append({"item": "assignment", "itemid": assignment["id"],
                                         "warningcode": "personal_deadline_unavailable"})
                    else:
                        status_warnings = self._warnings(status)
                        warnings.extend(status_warnings)
                        attempt = status.get("lastattempt", {})
                        # Missing data is unknown, never assume no extension.
                        if attempt.get("extensionduedate") is not None and not status_warnings:
                            extension = attempt["extensionduedate"]
                            item["extension_due_at"] = self._date(extension)
                            item["effective_due_at"] = self._date(max(due, extension))
                            item["personal_deadline_checked"] = True
                        else:
                            warnings.append({"item": "assignment", "itemid": assignment["id"],
                                             "warningcode": "personal_deadline_unavailable"})
                        submission = (attempt.get("teamsubmission")
                                      if assignment.get("teamsubmission")
                                      else attempt.get("submission"))
                        item["submission_status"] = (submission or {}).get("status")
                assignments.append(item)
        assignments.sort(key=lambda item: (item["effective_due_at"] or item["due_at"] or "9999",
                                           item["course_id"], item["id"]))
        return {"assignments": assignments, "warnings": warnings, "date_timezone": "UTC"}

    def _course_files(self, course_id: int):
        sections = self.call("core_course_get_contents", courseid=course_id)
        files = []
        for section in sections:
            for module in section.get("modules", []):
                for index, content in enumerate(module.get("contents", [])):
                    if content.get("type") != "file" or not content.get("fileurl"):
                        continue
                    files.append({
                        "id": f"{module['id']}:{index}",
                        "filename": content.get("filename", "unnamed"),
                        "mimetype": content.get("mimetype", ""),
                        "filesize": content.get("filesize", 0),
                        "section": section.get("name", ""),
                        "module": module.get("name", ""),
                        "_url": content["fileurl"],
                    })
        return files

    def list_files(self, course_id: int):
        return [{k: v for k, v in f.items() if k != "_url"}
                for f in self._course_files(course_id)]

    def _download(self, file_url: str) -> bytes:
        parts = urlsplit(file_url)
        base = urlsplit(BASE_URL)
        if (parts.scheme != "https" or parts.netloc != base.netloc
                or parts.username is not None or parts.password is not None):
            raise MoodleError("Moodle provided a file link from an unexpected origin.")
        if parts.path.startswith("/webservice/pluginfile.php/"):
            path = parts.path
        elif parts.path.startswith("/pluginfile.php/"):
            path = "/webservice" + parts.path
        else:
            raise MoodleError("This Moodle file URL is not a supported pluginfile URL.")
        existing_params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                           if k.lower() != "token"]
        url = urlunsplit(("https", base.netloc, path, urlencode(existing_params), ""))
        try:
            with requests.get(url, params={"token": self.token},
                              stream=True, allow_redirects=False, timeout=45) as response:
                if 300 <= response.status_code < 400:
                    raise MoodleError("Moodle file URL redirected. Refusing to forward token.")
                response.raise_for_status()
                declared = int(response.headers.get("content-length", "0") or 0)
                if declared > MAX_FILE_BYTES:
                    raise MoodleError("File is larger than the 25 MB safety limit.")
                body = bytearray()
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_FILE_BYTES:
                        raise MoodleError("File is larger than the 25 MB safety limit.")
        except requests.RequestException as exc:
            raise MoodleError("Unable to download file from Moodle.") from exc
        return bytes(body)

    def read_file(self, course_id: int, file_id: str):
        file_item = next((f for f in self._course_files(course_id)
                          if f["id"] == file_id), None)
        if file_item is None:
            raise MoodleError("File not found in that course. Run list_files again.")
        content = self._download(file_item["_url"])
        filename = file_item["filename"]
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            from docx import Document
            doc = Document(BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                paragraphs.extend(" | ".join(cell.text for cell in row.cells)
                                  for row in table.rows)
            text = "\n".join(paragraphs)
        elif suffix == ".pptx":
            from pptx import Presentation
            ppt = Presentation(BytesIO(content))
            slides = []
            for index, slide in enumerate(ppt.slides, 1):
                shapes = [shape.text for shape in slide.shapes if shape.has_text_frame]
                slides.append(f"Slide {index}\n" + "\n".join(shapes))
            text = "\n\n".join(slides)
        elif suffix in (".txt", ".md", ".csv", ".json", ".html", ".htm"):
            text = content.decode("utf-8-sig", errors="replace")
            if suffix in (".html", ".htm"):
                from bs4 import BeautifulSoup
                text = BeautifulSoup(text, "html.parser").get_text("\n", strip=True)
        else:
            raise MoodleError(f"Reading {suffix or 'this format'} is not implemented yet.")
        return {
            "filename": filename,
            "course_id": course_id,
            "text": text[:MAX_TEXT_CHARS],
            "truncated": len(text) > MAX_TEXT_CHARS,
            "characters_extracted": len(text),
            "note": "Scanned pages or images may require OCR, not included in this starter.",
        }
