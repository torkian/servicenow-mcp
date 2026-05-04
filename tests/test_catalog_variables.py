"""
Tests for the catalog item variables tools.
"""

import unittest
from unittest.mock import MagicMock, patch
import requests

from servicenow_mcp.tools.catalog_variables import (
    CreateCatalogItemVariableParams,
    CreateCatalogItemVariableSetParams,
    CreateCatalogVariableChoiceParams,
    DeleteCatalogItemVariableParams,
    ListCatalogItemVariablesParams,
    UpdateCatalogItemVariableParams,
    create_catalog_item_variable,
    create_catalog_item_variable_set,
    create_catalog_variable_choice,
    delete_catalog_item_variable,
    list_catalog_item_variables,
    update_catalog_item_variable,
)
from servicenow_mcp.utils.config import ServerConfig, AuthConfig, AuthType, BasicAuthConfig


class TestCatalogVariablesTools(unittest.TestCase):
    """
    Test the catalog item variables tools.
    """

    def setUp(self):
        """Set up the test environment."""
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            timeout=10,
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(
                    username="test_user",
                    password="test_password"
                )
            ),
        )
        self.auth_manager = MagicMock()
        self.auth_manager.get_headers.return_value = {"Content-Type": "application/json"}

    @patch("requests.post")
    def test_create_catalog_item_variable(self, mock_post):
        """Test create_catalog_item_variable function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "abc123",
                "name": "test_variable",
                "type": "string",
                "question_text": "Test Variable",
                "mandatory": "false",
            }
        }
        mock_post.return_value = mock_response

        # Create test params
        params = CreateCatalogItemVariableParams(
            catalog_item_id="item123",
            name="test_variable",
            type="string",
            label="Test Variable",
            mandatory=False,
        )

        # Call function
        result = create_catalog_item_variable(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.variable_id, "abc123")
        self.assertIsNotNone(result.details)

        # Verify mock was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[0][0], f"{self.config.instance_url}/api/now/table/item_option_new"
        )
        self.assertEqual(call_args[1]["json"]["cat_item"], "item123")
        self.assertEqual(call_args[1]["json"]["name"], "test_variable")
        self.assertEqual(call_args[1]["json"]["type"], "string")
        self.assertEqual(call_args[1]["json"]["question_text"], "Test Variable")
        self.assertEqual(call_args[1]["json"]["mandatory"], "false")

    @patch("requests.post")
    def test_create_catalog_item_variable_with_optional_params(self, mock_post):
        """Test create_catalog_item_variable function with optional parameters."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "abc123",
                "name": "test_variable",
                "type": "reference",
                "question_text": "Test Reference",
                "mandatory": "true",
                "reference": "sys_user",
                "reference_qual": "active=true",
                "help_text": "Select a user",
                "default_value": "admin",
                "description": "Reference to a user",
                "order": 100,
            }
        }
        mock_post.return_value = mock_response

        # Create test params with optional fields
        params = CreateCatalogItemVariableParams(
            catalog_item_id="item123",
            name="test_variable",
            type="reference",
            label="Test Reference",
            mandatory=True,
            help_text="Select a user",
            default_value="admin",
            description="Reference to a user",
            order=100,
            reference_table="sys_user",
            reference_qualifier="active=true",
        )

        # Call function
        result = create_catalog_item_variable(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.variable_id, "abc123")

        # Verify mock was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["reference"], "sys_user")
        self.assertEqual(call_args[1]["json"]["reference_qual"], "active=true")
        self.assertEqual(call_args[1]["json"]["help_text"], "Select a user")
        self.assertEqual(call_args[1]["json"]["default_value"], "admin")
        self.assertEqual(call_args[1]["json"]["description"], "Reference to a user")
        self.assertEqual(call_args[1]["json"]["order"], 100)

    @patch("requests.post")
    def test_create_catalog_item_variable_error(self, mock_post):
        """Test create_catalog_item_variable function with error."""
        # Configure mock to raise exception
        mock_post.side_effect = requests.RequestException("Test error")

        # Create test params
        params = CreateCatalogItemVariableParams(
            catalog_item_id="item123",
            name="test_variable",
            type="string",
            label="Test Variable",
        )

        # Call function
        result = create_catalog_item_variable(self.config, self.auth_manager, params)

        # Verify result
        self.assertFalse(result.success)
        self.assertTrue("failed" in result.message.lower())

    @patch("requests.get")
    def test_list_catalog_item_variables(self, mock_get):
        """Test list_catalog_item_variables function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "var1",
                    "name": "variable1",
                    "type": "string",
                    "question_text": "Variable 1",
                    "order": 100,
                    "mandatory": "true",
                },
                {
                    "sys_id": "var2",
                    "name": "variable2",
                    "type": "integer",
                    "question_text": "Variable 2",
                    "order": 200,
                    "mandatory": "false",
                },
            ]
        }
        mock_get.return_value = mock_response

        # Create test params
        params = ListCatalogItemVariablesParams(
            catalog_item_id="item123",
            include_details=True,
        )

        # Call function
        result = list_catalog_item_variables(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.count, 2)
        self.assertEqual(len(result.variables), 2)
        self.assertEqual(result.variables[0]["sys_id"], "var1")
        self.assertEqual(result.variables[1]["sys_id"], "var2")

        # Verify mock was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(
            call_args[0][0], f"{self.config.instance_url}/api/now/table/item_option_new"
        )
        self.assertEqual(
            call_args[1]["params"]["sysparm_query"], "cat_item=item123^ORDERBYorder"
        )
        self.assertEqual(call_args[1]["params"]["sysparm_display_value"], "true")
        self.assertEqual(call_args[1]["params"]["sysparm_exclude_reference_link"], "false")

    @patch("requests.get")
    def test_list_catalog_item_variables_with_pagination(self, mock_get):
        """Test list_catalog_item_variables function with pagination parameters."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": [{"sys_id": "var1"}]}
        mock_get.return_value = mock_response

        # Create test params with pagination
        params = ListCatalogItemVariablesParams(
            catalog_item_id="item123",
            include_details=False,
            limit=10,
            offset=20,
        )

        # Call function
        result = list_catalog_item_variables(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)

        # Verify mock was called correctly with pagination
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["sysparm_limit"], 10)
        self.assertEqual(call_args[1]["params"]["sysparm_offset"], 20)
        self.assertEqual(
            call_args[1]["params"]["sysparm_fields"],
            "sys_id,name,type,question_text,order,mandatory",
        )

    @patch("requests.get")
    def test_list_catalog_item_variables_error(self, mock_get):
        """Test list_catalog_item_variables function with error."""
        # Configure mock to raise exception
        mock_get.side_effect = requests.RequestException("Test error")

        # Create test params
        params = ListCatalogItemVariablesParams(
            catalog_item_id="item123",
        )

        # Call function
        result = list_catalog_item_variables(self.config, self.auth_manager, params)

        # Verify result
        self.assertFalse(result.success)
        self.assertTrue("failed" in result.message.lower())

    @patch("requests.patch")
    def test_update_catalog_item_variable(self, mock_patch):
        """Test update_catalog_item_variable function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "var1",
                "question_text": "Updated Variable",
                "mandatory": "true",
                "help_text": "This is help text",
            }
        }
        mock_patch.return_value = mock_response

        # Create test params
        params = UpdateCatalogItemVariableParams(
            variable_id="var1",
            label="Updated Variable",
            mandatory=True,
            help_text="This is help text",
        )

        # Call function
        result = update_catalog_item_variable(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.variable_id, "var1")
        self.assertIsNotNone(result.details)

        # Verify mock was called correctly
        mock_patch.assert_called_once()
        call_args = mock_patch.call_args
        self.assertEqual(
            call_args[0][0],
            f"{self.config.instance_url}/api/now/table/item_option_new/var1",
        )
        self.assertEqual(call_args[1]["json"]["question_text"], "Updated Variable")
        self.assertEqual(call_args[1]["json"]["mandatory"], "true")
        self.assertEqual(call_args[1]["json"]["help_text"], "This is help text")

    @patch("requests.patch")
    def test_update_catalog_item_variable_no_params(self, mock_patch):
        """Test update_catalog_item_variable function with no update parameters."""
        # Create test params with no updates (only ID)
        params = UpdateCatalogItemVariableParams(
            variable_id="var1",
        )

        # Call function
        result = update_catalog_item_variable(self.config, self.auth_manager, params)

        # Verify result - should fail since no update parameters provided
        self.assertFalse(result.success)
        self.assertEqual(result.message, "No update parameters provided")

        # Verify mock was not called
        mock_patch.assert_not_called()

    @patch("requests.patch")
    def test_update_catalog_item_variable_error(self, mock_patch):
        """Test update_catalog_item_variable function with error."""
        # Configure mock to raise exception
        mock_patch.side_effect = requests.RequestException("Test error")

        # Create test params
        params = UpdateCatalogItemVariableParams(
            variable_id="var1",
            label="Updated Variable",
        )

        # Call function
        result = update_catalog_item_variable(self.config, self.auth_manager, params)

        # Verify result
        self.assertFalse(result.success)
        self.assertTrue("failed" in result.message.lower())


class TestDeleteCatalogItemVariable(unittest.TestCase):
    """Tests for the delete_catalog_item_variable function."""

    def setUp(self):
        """Set up the test environment."""
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            timeout=10,
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(
                    username="test_user",
                    password="test_password"
                )
            ),
        )
        self.auth_manager = MagicMock()
        self.auth_manager.get_headers.return_value = {"Content-Type": "application/json"}

    @patch("requests.delete")
    def test_delete_catalog_item_variable_success(self, mock_delete):
        """Test successful deletion of a catalog item variable."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_delete.return_value = mock_response

        params = DeleteCatalogItemVariableParams(variable_id="var123")

        result = delete_catalog_item_variable(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.variable_id, "var123")
        self.assertIn("var123", result.message)

        mock_delete.assert_called_once()
        call_args = mock_delete.call_args
        self.assertEqual(
            call_args[0][0],
            f"{self.config.instance_url}/api/now/table/item_option_new/var123",
        )

    @patch("requests.delete")
    def test_delete_catalog_item_variable_error(self, mock_delete):
        """Test delete_catalog_item_variable when an error occurs."""
        mock_delete.side_effect = requests.RequestException("Connection error")

        params = DeleteCatalogItemVariableParams(variable_id="var123")

        result = delete_catalog_item_variable(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("failed", result.message.lower())

    @patch("requests.delete")
    def test_delete_catalog_item_variable_http_error(self, mock_delete):
        """Test delete_catalog_item_variable when HTTP 404 is returned."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_delete.return_value = mock_response

        params = DeleteCatalogItemVariableParams(variable_id="nonexistent")

        result = delete_catalog_item_variable(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("failed", result.message.lower())


class TestCreateCatalogVariableChoice(unittest.TestCase):
    """Tests for the create_catalog_variable_choice function."""

    def setUp(self):
        """Set up the test environment."""
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            timeout=10,
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(
                    username="test_user",
                    password="test_password",
                ),
            ),
        )
        self.auth_manager = MagicMock()
        self.auth_manager.get_headers.return_value = {"Content-Type": "application/json"}

    @patch("requests.post")
    def test_create_choice_success(self, mock_post):
        """Test successful creation of a catalog variable choice."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "choice123",
                "question": "var456",
                "text": "Option A",
                "value": "option_a",
                "inactive": "false",
            }
        }
        mock_post.return_value = mock_response

        params = CreateCatalogVariableChoiceParams(
            variable_id="var456",
            text="Option A",
            value="option_a",
        )

        result = create_catalog_variable_choice(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.choice_id, "choice123")
        self.assertIsNotNone(result.details)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[0][0],
            f"{self.config.instance_url}/api/now/table/question_choice",
        )
        self.assertEqual(call_args[1]["json"]["question"], "var456")
        self.assertEqual(call_args[1]["json"]["text"], "Option A")
        self.assertEqual(call_args[1]["json"]["value"], "option_a")
        self.assertEqual(call_args[1]["json"]["inactive"], "false")

    @patch("requests.post")
    def test_create_choice_with_optional_params(self, mock_post):
        """Test creation of a catalog variable choice with all optional fields."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "choice789",
                "question": "var456",
                "text": "Premium Option",
                "value": "premium",
                "order": "100",
                "price": "25.00",
                "price_type": "flat_fee",
                "inactive": "false",
            }
        }
        mock_post.return_value = mock_response

        params = CreateCatalogVariableChoiceParams(
            variable_id="var456",
            text="Premium Option",
            value="premium",
            order=100,
            price="25.00",
            price_type="flat_fee",
            inactive=False,
        )

        result = create_catalog_variable_choice(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.choice_id, "choice789")

        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["order"], 100)
        self.assertEqual(call_args[1]["json"]["price"], "25.00")
        self.assertEqual(call_args[1]["json"]["price_type"], "flat_fee")

    @patch("requests.post")
    def test_create_choice_inactive(self, mock_post):
        """Test that an inactive choice is sent with inactive=true."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "choice999",
                "question": "var456",
                "text": "Disabled Option",
                "value": "disabled",
                "inactive": "true",
            }
        }
        mock_post.return_value = mock_response

        params = CreateCatalogVariableChoiceParams(
            variable_id="var456",
            text="Disabled Option",
            value="disabled",
            inactive=True,
        )

        result = create_catalog_variable_choice(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["inactive"], "true")

    @patch("requests.post")
    def test_create_choice_omits_none_optional_fields(self, mock_post):
        """Optional fields not provided should not be included in the POST body."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "choiceX"}}
        mock_post.return_value = mock_response

        params = CreateCatalogVariableChoiceParams(
            variable_id="var1",
            text="Basic",
            value="basic",
        )

        create_catalog_variable_choice(self.config, self.auth_manager, params)

        call_args = mock_post.call_args
        body = call_args[1]["json"]
        self.assertNotIn("order", body)
        self.assertNotIn("price", body)
        self.assertNotIn("price_type", body)

    @patch("requests.post")
    def test_create_choice_error(self, mock_post):
        """Test create_catalog_variable_choice when a request error occurs."""
        mock_post.side_effect = requests.RequestException("Connection refused")

        params = CreateCatalogVariableChoiceParams(
            variable_id="var456",
            text="Option A",
            value="option_a",
        )

        result = create_catalog_variable_choice(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("failed", result.message.lower())

    @patch("requests.post")
    def test_create_choice_http_error(self, mock_post):
        """Test create_catalog_variable_choice when an HTTP error is returned."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_post.return_value = mock_response

        params = CreateCatalogVariableChoiceParams(
            variable_id="var456",
            text="Option A",
            value="option_a",
        )

        result = create_catalog_variable_choice(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("failed", result.message.lower())


class TestCreateCatalogItemVariableSet(unittest.TestCase):
    """Tests for the create_catalog_item_variable_set function."""

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
        self.auth_manager.get_headers.return_value = {"Content-Type": "application/json"}

    @patch("requests.post")
    def test_create_variable_set_success_no_link(self, mock_post):
        """Create a variable set without linking to a catalog item."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "set123", "name": "my_set", "title": "My Set", "type": "0"}
        }
        mock_post.return_value = mock_response

        params = CreateCatalogItemVariableSetParams(name="my_set", title="My Set")
        result = create_catalog_item_variable_set(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.variable_set_id, "set123")
        self.assertIsNone(result.link_id)
        self.assertIn("created successfully", result.message)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[0][0],
            "https://test.service-now.com/api/now/table/item_option_new_set",
        )
        body = call_args[1]["json"]
        self.assertEqual(body["name"], "my_set")
        self.assertEqual(body["title"], "My Set")
        self.assertEqual(body["type"], "0")  # local set
        self.assertEqual(body["active"], "true")

    @patch("requests.post")
    def test_create_variable_set_global(self, mock_post):
        """global_set=True sends type='1'."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "gset1", "type": "1"}}
        mock_post.return_value = mock_response

        params = CreateCatalogItemVariableSetParams(
            name="global_set", title="Global Set", global_set=True
        )
        result = create_catalog_item_variable_set(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        body = mock_post.call_args[1]["json"]
        self.assertEqual(body["type"], "1")

    @patch("requests.post")
    def test_create_variable_set_with_link(self, mock_post):
        """When catalog_item_id is provided the function makes two POSTs."""
        set_resp = MagicMock()
        set_resp.raise_for_status = MagicMock()
        set_resp.json.return_value = {"result": {"sys_id": "set456"}}

        link_resp = MagicMock()
        link_resp.raise_for_status = MagicMock()
        link_resp.json.return_value = {"result": {"sys_id": "link789"}}

        mock_post.side_effect = [set_resp, link_resp]

        params = CreateCatalogItemVariableSetParams(
            name="contact_info",
            title="Contact Information",
            catalog_item_id="item001",
            order=100,
        )
        result = create_catalog_item_variable_set(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.variable_set_id, "set456")
        self.assertEqual(result.link_id, "link789")
        self.assertIn("linked", result.message)

        self.assertEqual(mock_post.call_count, 2)
        link_call = mock_post.call_args_list[1]
        self.assertIn(
            "io_set_item",
            link_call[0][0],
        )
        link_body = link_call[1]["json"]
        self.assertEqual(link_body["sc_cat_item"], "item001")
        self.assertEqual(link_body["variable_set"], "set456")
        self.assertEqual(link_body["order"], 100)

    @patch("requests.post")
    def test_create_variable_set_with_description(self, mock_post):
        """Optional description is included in the POST body."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "setXYZ"}}
        mock_post.return_value = mock_response

        params = CreateCatalogItemVariableSetParams(
            name="details", title="Details", description="Extra details section"
        )
        create_catalog_item_variable_set(self.config, self.auth_manager, params)

        body = mock_post.call_args[1]["json"]
        self.assertEqual(body["description"], "Extra details section")

    @patch("requests.post")
    def test_create_variable_set_inactive(self, mock_post):
        """active=False sends active='false'."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "setZ"}}
        mock_post.return_value = mock_response

        params = CreateCatalogItemVariableSetParams(
            name="old_section", title="Old Section", active=False
        )
        result = create_catalog_item_variable_set(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        body = mock_post.call_args[1]["json"]
        self.assertEqual(body["active"], "false")

    @patch("requests.post")
    def test_create_variable_set_request_error(self, mock_post):
        """Network failure on the first POST returns failure."""
        mock_post.side_effect = requests.RequestException("Connection refused")

        params = CreateCatalogItemVariableSetParams(name="broken", title="Broken")
        result = create_catalog_item_variable_set(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("failed", result.message.lower())

    @patch("requests.post")
    def test_create_variable_set_http_error(self, mock_post):
        """HTTP error on the first POST returns failure."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_post.return_value = mock_response

        params = CreateCatalogItemVariableSetParams(name="forbidden", title="Forbidden")
        result = create_catalog_item_variable_set(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("failed", result.message.lower())

    @patch("requests.post")
    def test_create_variable_set_link_error(self, mock_post):
        """When the link POST fails the variable_set_id is still returned."""
        set_resp = MagicMock()
        set_resp.raise_for_status = MagicMock()
        set_resp.json.return_value = {"result": {"sys_id": "set999"}}

        link_resp = MagicMock()
        link_resp.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")
        mock_post.side_effect = [set_resp, link_resp]

        params = CreateCatalogItemVariableSetParams(
            name="partial", title="Partial", catalog_item_id="bad_item"
        )
        result = create_catalog_item_variable_set(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertEqual(result.variable_set_id, "set999")
        self.assertIn("link", result.message.lower())

    @patch("requests.post")
    def test_create_variable_set_no_order_in_link_when_not_set(self, mock_post):
        """order is not sent in the link body when not provided."""
        set_resp = MagicMock()
        set_resp.raise_for_status = MagicMock()
        set_resp.json.return_value = {"result": {"sys_id": "setA"}}

        link_resp = MagicMock()
        link_resp.raise_for_status = MagicMock()
        link_resp.json.return_value = {"result": {"sys_id": "linkA"}}

        mock_post.side_effect = [set_resp, link_resp]

        params = CreateCatalogItemVariableSetParams(
            name="no_order", title="No Order", catalog_item_id="itemX"
        )
        create_catalog_item_variable_set(self.config, self.auth_manager, params)

        link_body = mock_post.call_args_list[1][1]["json"]
        self.assertNotIn("order", link_body)


if __name__ == "__main__":
    unittest.main()