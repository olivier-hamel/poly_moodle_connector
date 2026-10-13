"""Check a private HTTP deployment without printing credentials or course text."""

import asyncio
import json
import re

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def tool_value(result):
    if result.isError:
        for item in result.content:
            if item.type == "text":
                match = re.search(r"Moodle API error: ([a-zA-Z0-9_]+)", item.text)
                if match:
                    print("Moodle error code:", match.group(1))
        raise RuntimeError("Moodle tool call failed; response omitted for privacy.")
    if isinstance(result.structuredContent, dict):
        return result.structuredContent.get("result", result.structuredContent)
    values = [json.loads(item.text) for item in result.content if item.type == "text"]
    if values:
        return values[0] if len(values) == 1 else values
    raise RuntimeError("Tool returned no JSON text.")


async def main():
    async with streamablehttp_client("http://127.0.0.1:8000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "list_courses", "list_files", "read_file", "list_events", "list_assignments",
            }
            print("MCP HTTP handshake and five-tool discovery: PASS")
            courses = tool_value(await session.call_tool("list_courses", {}))
            print("Moodle authentication and course listing: PASS")
            print("Accessible course count:", len(courses))
            if courses:
                files = tool_value(await session.call_tool("list_files", {
                    "course_id": courses[0]["id"],
                }))
                print("First course file listing: PASS")
                print("Attachment count:", len(files))
                events = tool_value(await session.call_tool("list_events", {
                    "course_id": courses[0]["id"],
                }))
                print("First course calendar event count:", len(events["events"]))
                print("Calendar warning count:", len(events["warnings"]))
                assignments = tool_value(await session.call_tool("list_assignments", {
                    "course_id": courses[0]["id"],
                }))
                print("First course assignment count:", len(assignments["assignments"]))
                print("Assignment warning count:", len(assignments["warnings"]))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("Deployment check failed:", type(exc).__name__)
        raise SystemExit(1) from None
