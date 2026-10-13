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
