"""Local read-only MCP server. Stdio only; not safe to expose publicly as-is."""

from mcp.server.fastmcp import FastMCP
from moodle_client import MoodleClient, load_token

mcp = FastMCP("Poly Moodle (read-only)")


def client() -> MoodleClient:
    return MoodleClient(load_token())


@mcp.tool()
def list_courses() -> list[dict]:
    """List the Moodle courses in which the current student is enrolled."""
    return client().list_courses()


@mcp.tool()
def list_events(course_id: int | None = None, time_start: int | None = None,
                time_end: int | None = None) -> dict:
    """List visible Moodle calendar events, including your group events.

    Omit course_id for all enrolled courses plus personal/site/category events.
    Optional time_start/time_end are Unix timestamps in seconds; default is now
    through 90 days ahead. Dates are ISO 8601 UTC; convert to the user's timezone.
    Check warnings before claiming the calendar is complete.
    """
    return client().list_events(course_id, time_start, time_end)


@mcp.tool()
def list_assignments(course_id: int | None = None,
                     include_personal_deadlines: bool = True) -> dict:
    """List Moodle submission boxes, due dates, opening dates and cutoff dates.

    Omit course_id for all enrolled courses. By default also checks your personal
    extension and submission status (one extra API call per submission box).
    effective_due_at is verified only when personal_deadline_checked is true;
    otherwise due_at is the Moodle assignment date, with extensions unverified.
    Zero/unset dates become null. cutoff_at is the closing date, distinct from
    due_at. Dates are ISO 8601 UTC; convert to the user's timezone. Includes past
    assignments and assignments without a deadline. Check warnings for omissions.
    """
    return client().list_assignments(course_id, include_personal_deadlines)


@mcp.tool()
def list_files(course_id: int) -> list[dict]:
    """List the documents and file attachments in one Moodle course."""
    return client().list_files(course_id)


@mcp.tool()
def read_file(course_id: int, file_id: str) -> dict:
    """Read one listed PDF, Word document, PowerPoint or text file from Moodle.

    Get file_id from list_files for the same course. Output is limited to 50,000
    characters. No submissions, grading, or modifications are supported.
    """
    return client().read_file(course_id, file_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
