"""Coverage tests for bulk_tools.py — defensive guard lines and helper edge cases."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.bulk_tools import (
    BulkUpdateChangeRequestsParams,
    BulkUpdateChangeTasksParams,
    BulkUpdateIncidentsParams,
    BulkUpdateProblemTasksParams,
    BulkUpdateProblemsParams,
    BulkUpdateRequestItemsParams,
    _resolve_change_request_numbers,
    _resolve_change_task_numbers,
    _resolve_incident_numbers,
    _resolve_problem_numbers,
    _resolve_problem_task_numbers,
    _resolve_request_item_numbers,
    bulk_update_change_requests,
    bulk_update_change_tasks,
    bulk_update_incidents,
    bulk_update_problem_tasks,
    bulk_update_problems,
    bulk_update_request_items,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

_AUTH_CONFIG = AuthConfig(
    type=AuthType.BASIC,
    basic=BasicAuthConfig(username="admin", password="password"),
)
_FAKE_HEADERS = {"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="}


def _config() -> ServerConfig:
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=_AUTH_CONFIG)


def _auth() -> MagicMock:
    m = MagicMock(spec=AuthManager)
    m.get_headers.return_value = _FAKE_HEADERS
    return m


class _TruthyEmptyIterable:
    """Passes early boolean/length guards but yields no items when iterated.

    Used to exercise the "No valid updates to execute" defensive guard.
    """

    def __len__(self):
        return 1

    def __bool__(self):
        return True

    def __iter__(self):
        return iter([])


def _params_with_empty_iterable(cls):
    """Build a mock Params object whose .updates is truthy but iterates empty."""
    p = MagicMock(spec=cls)
    p.updates = _TruthyEmptyIterable()
    return p


class TestNoValidUpdatesGuard(unittest.TestCase):
    """The 'No valid updates to execute' guard fires when updates passes the
    length checks but the loop produces no batch requests and no unresolved IDs.
    """

    def test_bulk_update_incidents_no_valid_updates(self):
        params = _params_with_empty_iterable(BulkUpdateIncidentsParams)
        result = bulk_update_incidents(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No valid updates to execute")

    def test_bulk_update_change_requests_no_valid_updates(self):
        params = _params_with_empty_iterable(BulkUpdateChangeRequestsParams)
        result = bulk_update_change_requests(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No valid updates to execute")

    def test_bulk_update_problems_no_valid_updates(self):
        params = _params_with_empty_iterable(BulkUpdateProblemsParams)
        result = bulk_update_problems(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No valid updates to execute")

    def test_bulk_update_problem_tasks_no_valid_updates(self):
        params = _params_with_empty_iterable(BulkUpdateProblemTasksParams)
        result = bulk_update_problem_tasks(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No valid updates to execute")

    def test_bulk_update_change_tasks_no_valid_updates(self):
        params = _params_with_empty_iterable(BulkUpdateChangeTasksParams)
        result = bulk_update_change_tasks(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No valid updates to execute")

    def test_bulk_update_request_items_no_valid_updates(self):
        params = _params_with_empty_iterable(BulkUpdateRequestItemsParams)
        result = bulk_update_request_items(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No valid updates to execute")


def _mock_get_response(results):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"result": results}
    return m


class TestResolveIncidentNumbers(unittest.TestCase):

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_success_returns_mapping(self, mock_req):
        mock_req.return_value = _mock_get_response([
            {"number": "INC0001", "sys_id": "a" * 32},
            {"number": "INC0002", "sys_id": "b" * 32},
        ])
        result = _resolve_incident_numbers(_config(), _auth(), ["INC0001", "INC0002"])
        self.assertEqual(result["INC0001"], "a" * 32)
        self.assertEqual(result["INC0002"], "b" * 32)

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_empty_result_returns_empty_dict(self, mock_req):
        mock_req.return_value = _mock_get_response([])
        result = _resolve_incident_numbers(_config(), _auth(), ["INC0001"])
        self.assertEqual(result, {})

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_http_error_propagates(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        mock_req.return_value = mock_resp
        with self.assertRaises(requests.HTTPError):
            _resolve_incident_numbers(_config(), _auth(), ["INC0001"])


class TestResolveChangeRequestNumbers(unittest.TestCase):

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_success_returns_mapping(self, mock_req):
        mock_req.return_value = _mock_get_response([
            {"number": "CHG0001", "sys_id": "c" * 32},
        ])
        result = _resolve_change_request_numbers(_config(), _auth(), ["CHG0001"])
        self.assertEqual(result["CHG0001"], "c" * 32)

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_empty_result_returns_empty_dict(self, mock_req):
        mock_req.return_value = _mock_get_response([])
        result = _resolve_change_request_numbers(_config(), _auth(), ["CHG0001"])
        self.assertEqual(result, {})

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_http_error_propagates(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        mock_req.return_value = mock_resp
        with self.assertRaises(requests.HTTPError):
            _resolve_change_request_numbers(_config(), _auth(), ["CHG0001"])


class TestResolveProblemNumbers(unittest.TestCase):

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_success_returns_mapping(self, mock_req):
        mock_req.return_value = _mock_get_response([
            {"number": "PRB0001", "sys_id": "d" * 32},
        ])
        result = _resolve_problem_numbers(_config(), _auth(), ["PRB0001"])
        self.assertEqual(result["PRB0001"], "d" * 32)

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_empty_result_returns_empty_dict(self, mock_req):
        mock_req.return_value = _mock_get_response([])
        result = _resolve_problem_numbers(_config(), _auth(), ["PRB0001"])
        self.assertEqual(result, {})

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_http_error_propagates(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("503")
        mock_req.return_value = mock_resp
        with self.assertRaises(requests.HTTPError):
            _resolve_problem_numbers(_config(), _auth(), ["PRB0001"])


class TestResolveProblemTaskNumbers(unittest.TestCase):

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_success_returns_mapping(self, mock_req):
        mock_req.return_value = _mock_get_response([
            {"number": "PTASK0001", "sys_id": "e" * 32},
        ])
        result = _resolve_problem_task_numbers(_config(), _auth(), ["PTASK0001"])
        self.assertEqual(result["PTASK0001"], "e" * 32)

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_empty_result_returns_empty_dict(self, mock_req):
        mock_req.return_value = _mock_get_response([])
        result = _resolve_problem_task_numbers(_config(), _auth(), ["PTASK0001"])
        self.assertEqual(result, {})

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_http_error_propagates(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        mock_req.return_value = mock_resp
        with self.assertRaises(requests.HTTPError):
            _resolve_problem_task_numbers(_config(), _auth(), ["PTASK0001"])


class TestResolveChangeTaskNumbers(unittest.TestCase):

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_success_returns_mapping(self, mock_req):
        mock_req.return_value = _mock_get_response([
            {"number": "CTASK0001", "sys_id": "f" * 32},
        ])
        result = _resolve_change_task_numbers(_config(), _auth(), ["CTASK0001"])
        self.assertEqual(result["CTASK0001"], "f" * 32)

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_empty_result_returns_empty_dict(self, mock_req):
        mock_req.return_value = _mock_get_response([])
        result = _resolve_change_task_numbers(_config(), _auth(), ["CTASK0001"])
        self.assertEqual(result, {})

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_http_error_propagates(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("503")
        mock_req.return_value = mock_resp
        with self.assertRaises(requests.HTTPError):
            _resolve_change_task_numbers(_config(), _auth(), ["CTASK0001"])


class TestResolveRequestItemNumbers(unittest.TestCase):

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_success_returns_mapping(self, mock_req):
        mock_req.return_value = _mock_get_response([
            {"number": "RITM0001", "sys_id": "0" * 32},
        ])
        result = _resolve_request_item_numbers(_config(), _auth(), ["RITM0001"])
        self.assertEqual(result["RITM0001"], "0" * 32)

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_empty_result_returns_empty_dict(self, mock_req):
        mock_req.return_value = _mock_get_response([])
        result = _resolve_request_item_numbers(_config(), _auth(), ["RITM0001"])
        self.assertEqual(result, {})

    @patch("servicenow_mcp.tools.bulk_tools._make_request")
    def test_http_error_propagates(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        mock_req.return_value = mock_resp
        with self.assertRaises(requests.HTTPError):
            _resolve_request_item_numbers(_config(), _auth(), ["RITM0001"])


if __name__ == "__main__":
    unittest.main()
