"""Tests for list_change_tasks, create_change_task, cancel_change_request, and reopen_change_request tools."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    CancelChangeRequestParams,
    CreateChangeTaskParams,
    ListChangeTasksParams,
    ReopenChangeRequestParams,
    _resolve_change_request_sys_id,
    cancel_change_request,
    create_change_task,
    list_change_tasks,
    reopen_change_request,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "b" * 32
FAKE_CHG_NUMBER = "CHG0001234"


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return auth


def _ok(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _err(status_code):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"error": {"message": "Not Found", "detail": ""}}
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


class TestResolveChangeRequestSysId(unittest.TestCase):
    """Unit tests for the internal helper."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_passthrough_on_hex32(self, mock_req):
        result = _resolve_change_request_sys_id("https://x.sn.com", {}, FAKE_SYS_ID)
        self.assertEqual(result, FAKE_SYS_ID)
        mock_req.assert_not_called()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_lookup_by_number(self, mock_req):
        mock_req.return_value = _ok({"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_change_request_sys_id("https://x.sn.com", {}, FAKE_CHG_NUMBER)
        self.assertEqual(result, FAKE_SYS_ID)
        call_kwargs = mock_req.call_args[1]
        self.assertIn(f"number={FAKE_CHG_NUMBER}", call_kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_none_when_not_found(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        result = _resolve_change_request_sys_id("https://x.sn.com", {}, FAKE_CHG_NUMBER)
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_none_on_request_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = _resolve_change_request_sys_id("https://x.sn.com", {}, FAKE_CHG_NUMBER)
        self.assertIsNone(result)


class TestListChangeTasks(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_list_by_sys_id(self, mock_req):
        tasks = [{"sys_id": "t1", "number": "CTASK0001"}, {"sys_id": "t2", "number": "CTASK0002"}]
        mock_req.return_value = _ok({"result": tasks})

        params = {"change_request_id": FAKE_SYS_ID, "limit": 10, "offset": 0}
        result = list_change_tasks(self.auth, self.config, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["tasks"]), 2)
        self.assertFalse(result["has_more"])

        call_kwargs = mock_req.call_args[1]
        self.assertIn(f"change_request={FAKE_SYS_ID}", call_kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_list_by_change_number_resolves(self, mock_req):
        mock_req.side_effect = [
            _ok({"result": [{"sys_id": FAKE_SYS_ID}]}),
            _ok({"result": [{"sys_id": "t1", "number": "CTASK0001"}]}),
        ]

        params = {"change_request_id": FAKE_CHG_NUMBER}
        result = list_change_tasks(self.auth, self.config, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_list_with_state_filter(self, mock_req):
        mock_req.return_value = _ok({"result": []})

        params = {"change_request_id": FAKE_SYS_ID, "state": "2"}
        result = list_change_tasks(self.auth, self.config, params)

        self.assertTrue(result["success"])
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("state=2", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_list_has_more_flag(self, mock_req):
        tasks = [{"sys_id": f"t{i}"} for i in range(5)]
        mock_req.return_value = _ok({"result": tasks})

        params = {"change_request_id": FAKE_SYS_ID, "limit": 5}
        result = list_change_tasks(self.auth, self.config, params)

        self.assertTrue(result["has_more"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_list_change_not_found(self, mock_req):
        mock_req.return_value = _ok({"result": []})

        params = {"change_request_id": FAKE_CHG_NUMBER}
        result = list_change_tasks(self.auth, self.config, params)

        self.assertFalse(result["success"])
        self.assertIn(FAKE_CHG_NUMBER, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_list_api_error(self, mock_req):
        # FAKE_SYS_ID is 32 hex chars so resolver returns it without API call.
        # Only the list call happens and it raises.
        mock_req.side_effect = requests.exceptions.RequestException("network fail")

        params = {"change_request_id": FAKE_SYS_ID}
        result = list_change_tasks(self.auth, self.config, params)
        self.assertFalse(result["success"])
        self.assertIn("Error listing change tasks", result["message"])

    def test_list_missing_required_param(self):
        result = list_change_tasks(self.auth, self.config, {})
        self.assertFalse(result["success"])

    def test_list_params_model_defaults(self):
        p = ListChangeTasksParams(change_request_id="CHG0001")
        self.assertEqual(p.limit, 10)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.state)


class TestCreateChangeTask(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_minimal(self, mock_req):
        created = {
            "sys_id": "t1",
            "number": "CTASK0001",
            "short_description": "Fix it",
            "state": "1",
            "assigned_to": None,
            "assignment_group": None,
        }
        mock_req.return_value = _ok({"result": created})

        params = {"change_request_id": FAKE_SYS_ID, "short_description": "Fix it"}
        result = create_change_task(self.auth, self.config, params)

        self.assertTrue(result["success"])
        self.assertIn("CTASK0001", result["message"])
        self.assertEqual(result["task"]["number"], "CTASK0001")
        self.assertEqual(result["task"]["change_request"], FAKE_SYS_ID)

        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["json"]["change_request"], FAKE_SYS_ID)
        self.assertEqual(call_kwargs["json"]["short_description"], "Fix it")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_with_all_optional_fields(self, mock_req):
        mock_req.side_effect = [
            _ok({"result": [{"sys_id": FAKE_SYS_ID}]}),
            _ok(
                {
                    "result": {
                        "sys_id": "t2",
                        "number": "CTASK0002",
                        "short_description": "Deploy",
                        "state": "2",
                        "assigned_to": "user1",
                        "assignment_group": "grp1",
                    }
                }
            ),
        ]

        params = {
            "change_request_id": FAKE_CHG_NUMBER,
            "short_description": "Deploy",
            "description": "Deploy the thing",
            "assigned_to": "user1",
            "assignment_group": "grp1",
            "state": "2",
            "planned_start_date": "2026-05-20 09:00:00",
            "planned_end_date": "2026-05-20 17:00:00",
            "work_notes": "Starting deployment",
        }
        result = create_change_task(self.auth, self.config, params)

        self.assertTrue(result["success"])
        body = mock_req.call_args_list[1][1]["json"]
        self.assertEqual(body["description"], "Deploy the thing")
        self.assertEqual(body["assigned_to"], "user1")
        self.assertEqual(body["assignment_group"], "grp1")
        self.assertEqual(body["state"], "2")
        self.assertEqual(body["planned_start_date"], "2026-05-20 09:00:00")
        self.assertEqual(body["planned_end_date"], "2026-05-20 17:00:00")
        self.assertEqual(body["work_notes"], "Starting deployment")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_change_not_found(self, mock_req):
        mock_req.return_value = _ok({"result": []})

        params = {"change_request_id": FAKE_CHG_NUMBER, "short_description": "Task"}
        result = create_change_task(self.auth, self.config, params)

        self.assertFalse(result["success"])
        self.assertIn(FAKE_CHG_NUMBER, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_api_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("network fail")

        params = {"change_request_id": FAKE_SYS_ID, "short_description": "Task"}
        result = create_change_task(self.auth, self.config, params)

        self.assertFalse(result["success"])
        self.assertIn("Error creating change task", result["message"])

    def test_create_missing_required_params(self):
        result = create_change_task(self.auth, self.config, {})
        self.assertFalse(result["success"])

        result = create_change_task(self.auth, self.config, {"change_request_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    def test_create_params_model(self):
        p = CreateChangeTaskParams(change_request_id="CHG0001", short_description="Do it")
        self.assertEqual(p.change_request_id, "CHG0001")
        self.assertEqual(p.short_description, "Do it")
        self.assertIsNone(p.description)
        self.assertIsNone(p.state)

    def test_create_params_date_validation(self):
        p = CreateChangeTaskParams(
            change_request_id="CHG0001",
            short_description="Test",
            planned_start_date="2026-05-20 09:00:00",
        )
        self.assertEqual(p.planned_start_date, "2026-05-20 09:00:00")

    def test_create_params_invalid_date(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            CreateChangeTaskParams(
                change_request_id="CHG0001",
                short_description="Test",
                planned_start_date="not-a-date",
            )


class TestCancelChangeRequest(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_cancel_by_sys_id(self, mock_req):
        record = {"sys_id": FAKE_SYS_ID, "number": "CHG0001234", "state": "-1"}
        mock_req.return_value = _ok({"result": record})

        result = cancel_change_request(self.auth, self.config, {"change_id": FAKE_SYS_ID})

        self.assertTrue(result["success"])
        self.assertIn("CHG0001234", result["message"])
        self.assertEqual(result["change_request"]["state"], "-1")

        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["state"], "-1")
        self.assertNotIn("work_notes", body)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_cancel_with_reason(self, mock_req):
        record = {"sys_id": FAKE_SYS_ID, "number": "CHG0001234", "state": "-1"}
        mock_req.return_value = _ok({"result": record})

        result = cancel_change_request(
            self.auth,
            self.config,
            {"change_id": FAKE_SYS_ID, "cancellation_reason": "No longer needed"},
        )

        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["work_notes"], "No longer needed")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_cancel_by_number_resolves(self, mock_req):
        record = {"sys_id": FAKE_SYS_ID, "number": FAKE_CHG_NUMBER, "state": "-1"}
        mock_req.side_effect = [
            _ok({"result": [{"sys_id": FAKE_SYS_ID}]}),
            _ok({"result": record}),
        ]

        result = cancel_change_request(self.auth, self.config, {"change_id": FAKE_CHG_NUMBER})

        self.assertTrue(result["success"])
        patch_kwargs = mock_req.call_args[1]
        self.assertIn(
            FAKE_SYS_ID, patch_kwargs["url"] if "url" in patch_kwargs else mock_req.call_args[0][1]
        )

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_cancel_not_found(self, mock_req):
        mock_req.return_value = _ok({"result": []})

        result = cancel_change_request(self.auth, self.config, {"change_id": FAKE_CHG_NUMBER})

        self.assertFalse(result["success"])
        self.assertIn(FAKE_CHG_NUMBER, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_cancel_api_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("network fail")

        result = cancel_change_request(self.auth, self.config, {"change_id": FAKE_SYS_ID})

        self.assertFalse(result["success"])
        self.assertIn("Error cancelling change request", result["message"])

    def test_cancel_missing_change_id(self):
        result = cancel_change_request(self.auth, self.config, {})
        self.assertFalse(result["success"])

    def test_cancel_params_model(self):
        p = CancelChangeRequestParams(change_id="CHG0001")
        self.assertEqual(p.change_id, "CHG0001")
        self.assertIsNone(p.cancellation_reason)

    def test_cancel_params_with_reason(self):
        p = CancelChangeRequestParams(change_id="CHG0001", cancellation_reason="Project shelved")
        self.assertEqual(p.cancellation_reason, "Project shelved")


class TestReopenChangeRequest(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_reopen_defaults_to_new(self, mock_req):
        record = {"sys_id": FAKE_SYS_ID, "number": "CHG0001234", "state": "-5"}
        mock_req.return_value = _ok({"result": record})

        result = reopen_change_request(self.auth, self.config, {"change_id": FAKE_SYS_ID})

        self.assertTrue(result["success"])
        self.assertIn("New", result["message"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["state"], "-5")
        self.assertNotIn("work_notes", body)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_reopen_to_assess(self, mock_req):
        record = {"sys_id": FAKE_SYS_ID, "number": "CHG0001234", "state": "-4"}
        mock_req.return_value = _ok({"result": record})

        result = reopen_change_request(
            self.auth, self.config, {"change_id": FAKE_SYS_ID, "state": "-4"}
        )

        self.assertTrue(result["success"])
        self.assertIn("Assess", result["message"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["state"], "-4")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_reopen_with_work_notes(self, mock_req):
        record = {"sys_id": FAKE_SYS_ID, "number": "CHG0001234", "state": "-5"}
        mock_req.return_value = _ok({"result": record})

        result = reopen_change_request(
            self.auth,
            self.config,
            {"change_id": FAKE_SYS_ID, "work_notes": "Reopening after review"},
        )

        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["work_notes"], "Reopening after review")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_reopen_by_number_resolves(self, mock_req):
        record = {"sys_id": FAKE_SYS_ID, "number": FAKE_CHG_NUMBER, "state": "-5"}
        mock_req.side_effect = [
            _ok({"result": [{"sys_id": FAKE_SYS_ID}]}),
            _ok({"result": record}),
        ]

        result = reopen_change_request(self.auth, self.config, {"change_id": FAKE_CHG_NUMBER})

        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_reopen_not_found(self, mock_req):
        mock_req.return_value = _ok({"result": []})

        result = reopen_change_request(self.auth, self.config, {"change_id": FAKE_CHG_NUMBER})

        self.assertFalse(result["success"])
        self.assertIn(FAKE_CHG_NUMBER, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_reopen_api_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("network fail")

        result = reopen_change_request(self.auth, self.config, {"change_id": FAKE_SYS_ID})

        self.assertFalse(result["success"])
        self.assertIn("Error reopening change request", result["message"])

    def test_reopen_missing_change_id(self):
        result = reopen_change_request(self.auth, self.config, {})
        self.assertFalse(result["success"])

    def test_reopen_params_defaults(self):
        p = ReopenChangeRequestParams(change_id="CHG0001")
        self.assertEqual(p.state, "-5")
        self.assertIsNone(p.work_notes)

    def test_reopen_params_custom_state(self):
        p = ReopenChangeRequestParams(change_id="CHG0001", state="-4", work_notes="See notes")
        self.assertEqual(p.state, "-4")
        self.assertEqual(p.work_notes, "See notes")


if __name__ == "__main__":
    unittest.main()
