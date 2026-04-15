"""
Tests for the User Criteria tools.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.user_criteria_tools import (
    CreateUserCriteriaConditionParams,
    CreateUserCriteriaParams,
    UserCriteriaConditionResponse,
    UserCriteriaResponse,
    create_user_criteria,
    create_user_criteria_condition,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestCreateUserCriteria(unittest.TestCase):
    """Tests for the create_user_criteria function."""

    def setUp(self):
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            timeout=10,
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="test_user", password="test_password"),
            ),
        )
        self.auth_manager = MagicMock()
        self.auth_manager.get_headers.return_value = {
            "Content-Type": "application/json",
            "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ=",
        }

    # ------------------------------------------------------------------
    # Success paths
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_create_minimal(self, mock_post):
        """Create a user criteria with only the required name field."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "uc_001",
                "name": "IT Staff Only",
                "active": "true",
                "match_all": "false",
            }
        }
        mock_post.return_value = mock_response

        params = CreateUserCriteriaParams(name="IT Staff Only")
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.criteria_id, "uc_001")
        self.assertIn("IT Staff Only", result.message)
        self.assertIn("created successfully", result.message)

        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["name"], "IT Staff Only")
        self.assertEqual(sent["active"], "true")
        self.assertEqual(sent["match_all"], "false")
        # No optional fields sent
        for field in ("role", "user", "group", "department", "company", "location", "script"):
            self.assertNotIn(field, sent)

    @patch("requests.post")
    def test_create_with_role(self, mock_post):
        """Create a user criteria scoped to a specific role."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "uc_002", "name": "ITIL Users"}
        }
        mock_post.return_value = mock_response

        params = CreateUserCriteriaParams(
            name="ITIL Users",
            role="role_sys_id_itil",
        )
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.criteria_id, "uc_002")

        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["role"], "role_sys_id_itil")

    @patch("requests.post")
    def test_create_with_group(self, mock_post):
        """Create a user criteria scoped to a user group."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "uc_003", "name": "Help Desk Group"}
        }
        mock_post.return_value = mock_response

        params = CreateUserCriteriaParams(
            name="Help Desk Group",
            group="group_sys_id_helpdesk",
        )
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["group"], "group_sys_id_helpdesk")

    @patch("requests.post")
    def test_create_with_all_optional_fields(self, mock_post):
        """Create a user criteria with all optional fields populated."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "uc_004", "name": "Complex Criteria"}
        }
        mock_post.return_value = mock_response

        params = CreateUserCriteriaParams(
            name="Complex Criteria",
            active=True,
            match_all=True,
            role="role_id",
            user="user_id",
            group="group_id",
            department="dept_id",
            company="company_id",
            location="location_id",
        )
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["match_all"], "true")
        self.assertEqual(sent["role"], "role_id")
        self.assertEqual(sent["user"], "user_id")
        self.assertEqual(sent["group"], "group_id")
        self.assertEqual(sent["department"], "dept_id")
        self.assertEqual(sent["company"], "company_id")
        self.assertEqual(sent["location"], "location_id")

    @patch("requests.post")
    def test_create_with_script(self, mock_post):
        """Create a user criteria that uses an advanced script."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "uc_005", "name": "Scripted Criteria"}
        }
        mock_post.return_value = mock_response

        script = "return gs.getUser().getRecord().getValue('vip') == 'true';"
        params = CreateUserCriteriaParams(
            name="Scripted Criteria",
            script=script,
        )
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["script"], script)

    @patch("requests.post")
    def test_create_inactive(self, mock_post):
        """Create a user criteria that starts inactive."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "uc_006", "name": "Draft Criteria", "active": "false"}
        }
        mock_post.return_value = mock_response

        params = CreateUserCriteriaParams(name="Draft Criteria", active=False)
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["active"], "false")

    @patch("requests.post")
    def test_response_contains_details(self, mock_post):
        """Verify the full result payload is available in response.details."""
        payload = {
            "sys_id": "uc_007",
            "name": "My Criteria",
            "active": "true",
            "match_all": "false",
        }
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": payload}
        mock_post.return_value = mock_response

        params = CreateUserCriteriaParams(name="My Criteria")
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertIsNotNone(result.details)
        self.assertEqual(result.details["sys_id"], "uc_007")
        self.assertEqual(result.details["name"], "My Criteria")

    @patch("requests.post")
    def test_api_url_correct(self, mock_post):
        """Verify the correct ServiceNow table endpoint is called."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "uc_008"}}
        mock_post.return_value = mock_response

        params = CreateUserCriteriaParams(name="URL Check")
        create_user_criteria(self.config, self.auth_manager, params)

        call_url = mock_post.call_args.args[0]
        self.assertEqual(
            call_url, "https://test.service-now.com/api/now/table/user_criteria"
        )

    # ------------------------------------------------------------------
    # Failure paths
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_http_error_returns_failure(self, mock_post):
        """HTTP 4xx/5xx should return a failed response, not raise."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "403 Forbidden"
        )
        mock_post.return_value = mock_response

        params = CreateUserCriteriaParams(name="Forbidden Criteria")
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to create user criteria", result.message)
        self.assertIsNone(result.criteria_id)

    @patch("requests.post")
    def test_connection_error_returns_failure(self, mock_post):
        """Network-level errors should return a failed response."""
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        params = CreateUserCriteriaParams(name="Network Error Criteria")
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to create user criteria", result.message)
        self.assertIsNone(result.criteria_id)

    @patch("requests.post")
    def test_timeout_error_returns_failure(self, mock_post):
        """Timeout errors should return a failed response."""
        mock_post.side_effect = requests.Timeout("Request timed out")

        params = CreateUserCriteriaParams(name="Timeout Criteria")
        result = create_user_criteria(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to create user criteria", result.message)

    # ------------------------------------------------------------------
    # Pydantic model validation
    # ------------------------------------------------------------------

    def test_params_defaults(self):
        """Verify CreateUserCriteriaParams defaults are applied correctly."""
        params = CreateUserCriteriaParams(name="Defaults Test")
        self.assertEqual(params.name, "Defaults Test")
        self.assertTrue(params.active)
        self.assertFalse(params.match_all)
        self.assertIsNone(params.role)
        self.assertIsNone(params.user)
        self.assertIsNone(params.group)
        self.assertIsNone(params.department)
        self.assertIsNone(params.company)
        self.assertIsNone(params.location)
        self.assertIsNone(params.script)

    def test_response_model_success(self):
        """Verify UserCriteriaResponse can be constructed for a success case."""
        resp = UserCriteriaResponse(
            success=True,
            message="Created",
            criteria_id="abc123",
            details={"sys_id": "abc123"},
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.criteria_id, "abc123")

    def test_response_model_failure(self):
        """Verify UserCriteriaResponse can be constructed for a failure case."""
        resp = UserCriteriaResponse(
            success=False,
            message="Something went wrong",
        )
        self.assertFalse(resp.success)
        self.assertIsNone(resp.criteria_id)
        self.assertIsNone(resp.details)


class TestCreateUserCriteriaCondition(unittest.TestCase):
    """Tests for the create_user_criteria_condition function."""

    def setUp(self):
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            timeout=10,
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="test_user", password="test_password"),
            ),
        )
        self.auth_manager = MagicMock()
        self.auth_manager.get_headers.return_value = {
            "Content-Type": "application/json",
            "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ=",
        }

    def _make_mock_response(self, sys_id="cond_001"):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": sys_id,
                "user_criteria": "uc_001",
                "sc_cat_item": "item_001",
            }
        }
        return mock_response

    # ------------------------------------------------------------------
    # Success paths — catalog_item
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_catalog_item_can_see(self, mock_post):
        """Apply criteria to a catalog item with can_see visibility."""
        mock_post.return_value = self._make_mock_response("cond_001")

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_001",
            entity_type="catalog_item",
            entity_id="item_001",
            visibility="can_see",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.condition_id, "cond_001")
        self.assertIn("catalog_item", result.message)
        self.assertIn("can_see", result.message)

        call_url = mock_post.call_args.args[0]
        self.assertIn("sc_cat_item_user_criteria_mtom", call_url)

        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["user_criteria"], "uc_001")
        self.assertEqual(sent["sc_cat_item"], "item_001")

    @patch("requests.post")
    def test_catalog_item_cannot_see(self, mock_post):
        """Apply criteria to a catalog item with cannot_see visibility."""
        mock_post.return_value = self._make_mock_response("cond_002")

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_001",
            entity_type="catalog_item",
            entity_id="item_002",
            visibility="cannot_see",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.condition_id, "cond_002")
        self.assertIn("cannot_see", result.message)

        call_url = mock_post.call_args.args[0]
        self.assertIn("sc_cat_item_user_criteria_no_mtom", call_url)

    # ------------------------------------------------------------------
    # Success paths — category
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_category_can_see(self, mock_post):
        """Apply criteria to a catalog category with can_see visibility."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "cond_cat_001", "user_criteria": "uc_001", "sc_category": "cat_001"}
        }
        mock_post.return_value = mock_response

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_001",
            entity_type="category",
            entity_id="cat_001",
            visibility="can_see",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.condition_id, "cond_cat_001")

        call_url = mock_post.call_args.args[0]
        self.assertIn("sc_category_user_criteria_mtom", call_url)

        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["sc_category"], "cat_001")
        self.assertEqual(sent["user_criteria"], "uc_001")

    @patch("requests.post")
    def test_category_cannot_see(self, mock_post):
        """Apply criteria to a catalog category with cannot_see visibility."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "cond_cat_002"}}
        mock_post.return_value = mock_response

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_002",
            entity_type="category",
            entity_id="cat_002",
            visibility="cannot_see",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        call_url = mock_post.call_args.args[0]
        self.assertIn("sc_category_user_criteria_no_mtom", call_url)

    # ------------------------------------------------------------------
    # Success paths — catalog
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_catalog_can_see(self, mock_post):
        """Apply criteria to an entire catalog with can_see visibility."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "cond_sc_001"}}
        mock_post.return_value = mock_response

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_003",
            entity_type="catalog",
            entity_id="sc_001",
            visibility="can_see",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        call_url = mock_post.call_args.args[0]
        self.assertIn("sc_catalog_user_criteria_mtom", call_url)

        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["sc_catalog"], "sc_001")
        self.assertEqual(sent["user_criteria"], "uc_003")

    @patch("requests.post")
    def test_catalog_cannot_see(self, mock_post):
        """Apply criteria to an entire catalog with cannot_see visibility."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "cond_sc_002"}}
        mock_post.return_value = mock_response

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_004",
            entity_type="catalog",
            entity_id="sc_002",
            visibility="cannot_see",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        call_url = mock_post.call_args.args[0]
        self.assertIn("sc_catalog_user_criteria_no_mtom", call_url)

    # ------------------------------------------------------------------
    # Default visibility
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_default_visibility_is_can_see(self, mock_post):
        """Omitting visibility should default to can_see (allow-list)."""
        mock_post.return_value = self._make_mock_response()

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_001",
            entity_type="catalog_item",
            entity_id="item_001",
        )
        self.assertEqual(params.visibility, "can_see")

        result = create_user_criteria_condition(self.config, self.auth_manager, params)
        self.assertTrue(result.success)
        call_url = mock_post.call_args.args[0]
        self.assertIn("sc_cat_item_user_criteria_mtom", call_url)

    # ------------------------------------------------------------------
    # Response content
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_response_contains_details(self, mock_post):
        """Full result payload should be available in response.details."""
        payload = {
            "sys_id": "cond_007",
            "user_criteria": "uc_001",
            "sc_cat_item": "item_007",
        }
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": payload}
        mock_post.return_value = mock_response

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_001",
            entity_type="catalog_item",
            entity_id="item_007",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertIsNotNone(result.details)
        self.assertEqual(result.details["sys_id"], "cond_007")

    @patch("requests.post")
    def test_api_url_uses_instance_url(self, mock_post):
        """API call must use the configured instance URL."""
        mock_post.return_value = self._make_mock_response()

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_001",
            entity_type="catalog_item",
            entity_id="item_001",
        )
        create_user_criteria_condition(self.config, self.auth_manager, params)

        call_url = mock_post.call_args.args[0]
        self.assertTrue(call_url.startswith("https://test.service-now.com"))

    # ------------------------------------------------------------------
    # Failure paths
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_http_error_returns_failure(self, mock_post):
        """HTTP 4xx/5xx should return a failed response, not raise."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_post.return_value = mock_response

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_x",
            entity_type="catalog_item",
            entity_id="item_x",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to create user criteria condition", result.message)
        self.assertIsNone(result.condition_id)

    @patch("requests.post")
    def test_connection_error_returns_failure(self, mock_post):
        """Network-level errors should return a failed response."""
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_x",
            entity_type="category",
            entity_id="cat_x",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIsNone(result.condition_id)

    @patch("requests.post")
    def test_timeout_error_returns_failure(self, mock_post):
        """Timeout errors should return a failed response."""
        mock_post.side_effect = requests.Timeout("Request timed out")

        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_x",
            entity_type="catalog",
            entity_id="sc_x",
        )
        result = create_user_criteria_condition(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to create user criteria condition", result.message)

    # ------------------------------------------------------------------
    # Pydantic model validation
    # ------------------------------------------------------------------

    def test_params_defaults(self):
        """Verify CreateUserCriteriaConditionParams defaults."""
        params = CreateUserCriteriaConditionParams(
            user_criteria_id="uc_001",
            entity_type="catalog_item",
            entity_id="item_001",
        )
        self.assertEqual(params.visibility, "can_see")

    def test_response_model_success(self):
        """Verify UserCriteriaConditionResponse for success case."""
        resp = UserCriteriaConditionResponse(
            success=True,
            message="Created",
            condition_id="cond_abc",
            details={"sys_id": "cond_abc"},
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.condition_id, "cond_abc")

    def test_response_model_failure(self):
        """Verify UserCriteriaConditionResponse for failure case."""
        resp = UserCriteriaConditionResponse(
            success=False,
            message="Something went wrong",
        )
        self.assertFalse(resp.success)
        self.assertIsNone(resp.condition_id)
        self.assertIsNone(resp.details)


if __name__ == "__main__":
    unittest.main()
