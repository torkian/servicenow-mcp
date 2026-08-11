"""Tests for event_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.event_tools import (
    CreateEventParams,
    GetEventParams,
    ListEventsParams,
    _format_event,
    create_event,
    get_event,
    list_events,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_EVENT = {
    "sys_id": "ev001",
    "name": "incident.created",
    "parm1": "INC0001234",
    "parm2": "critical",
    "state": "0",
    "queue": "default",
    "process_on": "",
    "processed": "",
    "claimed_by": "",
    "fired_by": "admin",
    "instance": "dev99999",
    "table": "incident",
    "record": "inc_sys001",
    "error_string": "",
    "sys_created_on": "2026-08-11 09:00:00",
    "sys_created_by": "admin",
}

FAKE_EVENT_DICT_FIRED_BY = dict(FAKE_EVENT, fired_by={"display_value": "System Administrator", "value": "admin_sys_id"})


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth_manager():
    auth_manager = MagicMock(spec=AuthManager)
    auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    auth_manager.instance_url = "https://dev99999.service-now.com"
    return auth_manager


class TestFormatEvent(unittest.TestCase):
    def test_all_fields_present(self):
        result = _format_event(FAKE_EVENT)
        self.assertEqual(result["sys_id"], "ev001")
        self.assertEqual(result["name"], "incident.created")
        self.assertEqual(result["parm1"], "INC0001234")
        self.assertEqual(result["parm2"], "critical")
        self.assertEqual(result["state"], "pending")
        self.assertEqual(result["queue"], "default")
        self.assertEqual(result["fired_by"], "admin")
        self.assertEqual(result["table"], "incident")
        self.assertEqual(result["record"], "inc_sys001")
        self.assertEqual(result["created_on"], "2026-08-11 09:00:00")
        self.assertEqual(result["created_by"], "admin")

    def test_state_labels(self):
        for raw, label in [("0", "pending"), ("1", "processed"), ("2", "error"), ("3", "cancelled")]:
            result = _format_event(dict(FAKE_EVENT, state=raw))
            self.assertEqual(result["state"], label)

    def test_state_unknown(self):
        result = _format_event(dict(FAKE_EVENT, state="9"))
        self.assertEqual(result["state"], "9")

    def test_fired_by_dict_display_value(self):
        result = _format_event(FAKE_EVENT_DICT_FIRED_BY)
        self.assertEqual(result["fired_by"], "System Administrator")

    def test_fired_by_dict_value_fallback(self):
        record = dict(FAKE_EVENT, fired_by={"value": "admin_sys_id"})
        result = _format_event(record)
        self.assertEqual(result["fired_by"], "admin_sys_id")

    def test_missing_fields_return_none(self):
        result = _format_event({})
        for key in ("sys_id", "name", "parm1", "parm2", "queue", "fired_by", "table", "record", "error_string"):
            self.assertIsNone(result[key])


class TestListEvents(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.get")
    def test_list_returns_events(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_EVENT]}
        mock_get.return_value = mock_resp

        result = list_events(self.auth_manager, self.config, {"limit": 10, "offset": 0})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["events"][0]["sys_id"], "ev001")

    @patch("requests.get")
    def test_list_empty_result(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_get.return_value = mock_resp

        result = list_events(self.auth_manager, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["events"], [])

    @patch("requests.get")
    def test_list_with_name_filter(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_EVENT]}
        mock_get.return_value = mock_resp

        result = list_events(self.auth_manager, self.config, {"name": "incident.created"})
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("nameLIKEincident.created", query)

    @patch("requests.get")
    def test_list_with_state_filter(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_get.return_value = mock_resp

        result = list_events(self.auth_manager, self.config, {"state": "2"})
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("state=2", query)

    @patch("requests.get")
    def test_list_with_queue_filter(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_get.return_value = mock_resp

        result = list_events(self.auth_manager, self.config, {"queue": "default"})
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("queueLIKEdefault", query)

    @patch("requests.get")
    def test_list_with_fired_by_filter(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_get.return_value = mock_resp

        result = list_events(self.auth_manager, self.config, {"fired_by": "user_sys_id"})
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("fired_by=user_sys_id", query)

    @patch("requests.get")
    def test_list_with_date_range(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_get.return_value = mock_resp

        result = list_events(
            self.auth_manager,
            self.config,
            {"created_after": "2026-08-01", "created_before": "2026-08-11"},
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("sys_created_on>=2026-08-01", query)
        self.assertIn("sys_created_on<=2026-08-11", query)

    @patch("requests.get")
    def test_list_with_all_filters(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_get.return_value = mock_resp

        result = list_events(
            self.auth_manager,
            self.config,
            {"name": "incident", "state": "0", "queue": "default", "fired_by": "uid", "created_after": "2026-08-01"},
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("nameLIKEincident", query)
        self.assertIn("state=0", query)
        self.assertIn("queueLIKEdefault", query)
        self.assertIn("fired_by=uid", query)
        self.assertIn("sys_created_on>=2026-08-01", query)

    @patch("requests.get")
    def test_list_has_more_pagination(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_EVENT] * 5}
        mock_get.return_value = mock_resp

        result = list_events(self.auth_manager, self.config, {"limit": 5, "offset": 0})
        self.assertTrue(result["success"])
        self.assertTrue(result.get("has_more"))
        self.assertEqual(result.get("next_offset"), 5)

    @patch("requests.get")
    def test_list_request_exception(self, mock_get):
        mock_get.side_effect = req.exceptions.ConnectionError("timeout")

        result = list_events(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing events", result["message"])

    def test_list_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = list_events(auth_manager, server_config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_list_missing_headers(self):
        auth_manager = MagicMock()
        auth_manager.instance_url = "https://dev99999.service-now.com"
        del auth_manager.get_headers
        server_config = MagicMock()
        del server_config.instance_url
        del server_config.get_headers

        result = list_events(auth_manager, server_config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


class TestGetEvent(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.get")
    def test_get_event_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": FAKE_EVENT}
        mock_get.return_value = mock_resp

        result = get_event(self.auth_manager, self.config, {"sys_id": "ev001"})

        self.assertTrue(result["success"])
        self.assertEqual(result["event"]["sys_id"], "ev001")
        self.assertEqual(result["event"]["name"], "incident.created")
        self.assertEqual(result["event"]["state"], "pending")

    @patch("requests.get")
    def test_get_event_not_found_404(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        result = get_event(self.auth_manager, self.config, {"sys_id": "nonexistent"})
        self.assertFalse(result["success"])
        self.assertIn("nonexistent", result["message"])

    @patch("requests.get")
    def test_get_event_empty_result(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {}}
        mock_get.return_value = mock_resp

        result = get_event(self.auth_manager, self.config, {"sys_id": "ev001"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("requests.get")
    def test_get_event_request_exception(self, mock_get):
        mock_get.side_effect = req.exceptions.ConnectionError("timeout")

        result = get_event(self.auth_manager, self.config, {"sys_id": "ev001"})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving event", result["message"])

    def test_get_event_missing_sys_id(self):
        result = get_event(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])

    def test_get_event_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = get_event(auth_manager, server_config, {"sys_id": "ev001"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_get_event_missing_headers(self):
        auth_manager = MagicMock()
        auth_manager.instance_url = "https://dev99999.service-now.com"
        del auth_manager.get_headers
        server_config = MagicMock()
        del server_config.instance_url
        del server_config.get_headers

        result = get_event(auth_manager, server_config, {"sys_id": "ev001"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


class TestCreateEvent(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.post")
    def test_create_event_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"result": FAKE_EVENT}
        mock_post.return_value = mock_resp

        result = create_event(
            self.auth_manager,
            self.config,
            {"name": "incident.created", "parm1": "INC0001234"},
        )

        self.assertTrue(result["success"])
        self.assertIn("incident.created", result["message"])
        self.assertEqual(result["event"]["sys_id"], "ev001")

    @patch("requests.post")
    def test_create_event_all_params(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"result": FAKE_EVENT}
        mock_post.return_value = mock_resp

        result = create_event(
            self.auth_manager,
            self.config,
            {
                "name": "incident.created",
                "parm1": "INC0001234",
                "parm2": "critical",
                "queue": "default",
                "table": "incident",
                "record": "inc_sys001",
                "fired_by": "admin_sys_id",
            },
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_post.call_args
        body = call_kwargs[1]["json"]
        self.assertEqual(body["name"], "incident.created")
        self.assertEqual(body["parm1"], "INC0001234")
        self.assertEqual(body["parm2"], "critical")
        self.assertEqual(body["queue"], "default")
        self.assertEqual(body["table"], "incident")
        self.assertEqual(body["record"], "inc_sys001")
        self.assertEqual(body["fired_by"], "admin_sys_id")

    @patch("requests.post")
    def test_create_event_omits_none_fields(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"result": FAKE_EVENT}
        mock_post.return_value = mock_resp

        create_event(self.auth_manager, self.config, {"name": "task.completed"})

        call_kwargs = mock_post.call_args
        body = call_kwargs[1]["json"]
        self.assertNotIn("parm1", body)
        self.assertNotIn("parm2", body)
        self.assertNotIn("queue", body)
        self.assertNotIn("table", body)
        self.assertNotIn("record", body)

    @patch("requests.post")
    def test_create_event_request_exception(self, mock_post):
        mock_post.side_effect = req.exceptions.ConnectionError("timeout")

        result = create_event(self.auth_manager, self.config, {"name": "test.event"})
        self.assertFalse(result["success"])
        self.assertIn("Error creating event", result["message"])

    def test_create_event_missing_name(self):
        result = create_event(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])

    def test_create_event_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = create_event(auth_manager, server_config, {"name": "test.event"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_create_event_missing_headers(self):
        auth_manager = MagicMock()
        auth_manager.instance_url = "https://dev99999.service-now.com"
        del auth_manager.get_headers
        server_config = MagicMock()
        del server_config.instance_url
        del server_config.get_headers

        result = create_event(auth_manager, server_config, {"name": "test.event"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


class TestEventParams(unittest.TestCase):
    def test_list_params_defaults(self):
        p = ListEventsParams()
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.name)
        self.assertIsNone(p.state)
        self.assertIsNone(p.queue)
        self.assertIsNone(p.fired_by)
        self.assertIsNone(p.created_after)
        self.assertIsNone(p.created_before)

    def test_get_params_requires_sys_id(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GetEventParams()

    def test_get_params_valid(self):
        p = GetEventParams(sys_id="ev001")
        self.assertEqual(p.sys_id, "ev001")

    def test_create_params_requires_name(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            CreateEventParams()

    def test_create_params_valid_minimal(self):
        p = CreateEventParams(name="incident.created")
        self.assertEqual(p.name, "incident.created")
        self.assertIsNone(p.parm1)
        self.assertIsNone(p.parm2)

    def test_create_params_all_fields(self):
        p = CreateEventParams(
            name="task.completed",
            parm1="TASK001",
            parm2="info",
            queue="priority",
            table="task",
            record="task_sys001",
            fired_by="user_sys_id",
        )
        self.assertEqual(p.name, "task.completed")
        self.assertEqual(p.parm1, "TASK001")
        self.assertEqual(p.queue, "priority")


if __name__ == "__main__":
    unittest.main()
