"""Offline regression checks for calendar coverage and personal deadlines."""

import unittest
from unittest.mock import Mock, patch

from moodle_client import MoodleClient, MoodleError


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.client = MoodleClient("offline-test-token")

    def test_events_include_enrolled_courses_and_current_user_groups(self):
        self.client.list_courses = Mock(return_value=[{"id": 7, "shortname": "INF"}])
        self.client.call = Mock(side_effect=[
            {"groups": [{"id": 12}], "warnings": []},
            {"events": [{"id": 2, "courseid": 7, "timestart": 200},
                        {"id": 1, "courseid": 0, "timestart": 100}],
             "warnings": [{"warningcode": "partial", "message": "private trace"}]},
        ])
        result = self.client.list_events(time_start=50, time_end=300)
        params = self.client.call.call_args.kwargs
        self.assertEqual(params["events[courseids][0]"], 7)
        self.assertEqual(params["events[groupids][0]"], 12)
        self.assertEqual(params["options[userevents]"], 1)
        self.assertEqual([e["id"] for e in result["events"]], [1, 2])
        self.assertTrue(result["events"][0]["start_at"].endswith("+00:00"))
        self.assertNotIn("private trace", str(result))

    def test_course_filter_excludes_personal_site_and_category_events(self):
        self.client.list_courses = Mock(return_value=[{"id": 7, "shortname": "INF"}])
        self.client.call = Mock(side_effect=[{"groups": []}, {"events": [
            {"id": 1, "courseid": 0, "timestart": 100},
            {"id": 2, "courseid": 7, "timestart": 200},
        ]}])
        result = self.client.list_events(7, 50, 300)
        self.assertEqual([e["id"] for e in result["events"]], [2])
        self.assertEqual(self.client.call.call_args.kwargs["options[siteevents]"], 0)
        self.assertEqual(self.client.call.call_args_list[0].kwargs, {"courseid": 7})

    def test_invalid_time_bounds_fail_before_network(self):
        self.client.call = Mock()
        for start, end in [(-1, 100), (100, 100), (200, 100)]:
            with self.subTest(start=start, end=end), self.assertRaises(MoodleError):
                self.client.list_events(time_start=start, time_end=end)
        self.client.call.assert_not_called()

    def assignments_response(self):
        return {"courses": [{"id": 7, "shortname": "INF", "assignments": [
            {"id": 10, "cmid": 50, "name": "TP", "duedate": 200,
             "cutoffdate": 400, "teamsubmission": 1},
            {"id": 11, "cmid": 51, "name": "No date", "duedate": 0},
        ]}], "warnings": []}

    def test_extension_and_team_submission_with_zero_dates(self):
        self.client.call = Mock(side_effect=[self.assignments_response(),
            {"lastattempt": {"extensionduedate": 300,
                             "teamsubmission": {"status": "submitted"},
                             "submission": {"status": "new"}}},
            {"lastattempt": {"extensionduedate": 0}},
        ])
        result = self.client.list_assignments(7)
        first, second = result["assignments"]
        self.assertEqual(first["effective_due_at"], self.client._date(300))
        self.assertEqual(first["cutoff_at"], self.client._date(400))
        self.assertEqual(first["submission_status"], "submitted")
        self.assertTrue(first["personal_deadline_checked"])
        self.assertIsNone(second["due_at"])
        self.assertIsNone(second["effective_due_at"])
        self.assertTrue(second["personal_deadline_checked"])
        self.assertEqual(self.client.call.call_args_list[0].kwargs, {"courseids[0]": 7})
        self.assertEqual(self.client.call.call_args_list[1].kwargs, {"assignid": 10})

    def test_unavailable_or_missing_extension_is_not_reported_as_verified(self):
        self.client.call = Mock(side_effect=[self.assignments_response(),
                                             MoodleError("denied"), {}])
        result = self.client.list_assignments()
        self.assertEqual(len(result["warnings"]), 2)
        for assignment in result["assignments"]:
            self.assertFalse(assignment["personal_deadline_checked"])
            self.assertIsNone(assignment["effective_due_at"])

    def test_fast_list_does_not_fetch_personal_status(self):
        self.client.call = Mock(return_value=self.assignments_response())
        result = self.client.list_assignments(include_personal_deadlines=False)
        self.client.call.assert_called_once_with("mod_assign_get_assignments")
        self.assertFalse(result["assignments"][0]["personal_deadline_checked"])

    def test_null_extension_remains_unverified(self):
        self.client.call = Mock(side_effect=[self.assignments_response(),
            {"lastattempt": {"extensionduedate": None}},
            {"lastattempt": {"extensionduedate": 0}},
        ])
        result = self.client.list_assignments()
        first = next(a for a in result["assignments"] if a["id"] == 10)
        self.assertFalse(first["personal_deadline_checked"])
        self.assertIsNone(first["effective_due_at"])
        self.assertEqual(result["warnings"][0]["warningcode"], "personal_deadline_unavailable")

    def test_mcp_tool_discovery_and_delegation(self):
        import asyncio
        from server import mcp, list_assignments, list_events

        tools = asyncio.run(mcp.list_tools())
        self.assertEqual({tool.name for tool in tools}, {
            "list_courses", "list_files", "read_file", "list_events", "list_assignments",
        })
        with patch("server.client", return_value=self.client):
            self.client.list_events = Mock(return_value={"events": []})
            self.client.list_assignments = Mock(return_value={"assignments": []})
            self.assertEqual(list_events(7, 50, 300), {"events": []})
            self.assertEqual(list_assignments(7, False), {"assignments": []})
            self.client.list_events.assert_called_once_with(7, 50, 300)
            self.client.list_assignments.assert_called_once_with(7, False)

    def test_deployment_check_handles_structured_dictionary_results(self):
        from deploy.check_server import tool_value

        result = Mock(isError=False, structuredContent={"events": [], "warnings": []})
        self.assertEqual(tool_value(result), {"events": [], "warnings": []})
        result.structuredContent = {"result": [{"id": 7}]}
        self.assertEqual(tool_value(result), [{"id": 7}])
        result.structuredContent = None
        result.content = [Mock(type="text", text='{"assignments": [], "warnings": []}')]
        self.assertEqual(tool_value(result), {"assignments": [], "warnings": []})


if __name__ == "__main__":
    unittest.main()
