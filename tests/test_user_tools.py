"""
Tests for user management tools.
"""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.user_tools import (
    AddGroupMembersParams,
    CreateGroupParams,
    CreateUserParams,
    GetUserParams,
    ListCustomersParams,
    ListUsersParams,
    ListGroupsParams,
    RemoveGroupMembersParams,
    UpdateGroupParams,
    UpdateUserParams,
    add_group_members,
    _build_customer_query_variants,
    create_group,
    create_user,
    _fix_mojibake_text,
    _normalize_text_values,
    get_user,
    list_customers,
    list_users,
    list_groups,
    remove_group_members,
    update_group,
    update_user,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestUserTools(unittest.TestCase):
    """Tests for user management tools."""

    def setUp(self):
        """Set up test environment."""
        # Create config and auth manager
        self.config = ServerConfig(
            instance_url="https://example.service-now.com",
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="admin", password="password"),
            ),
        )
        self.auth_manager = AuthManager(self.config.auth)

        # Mock auth_manager.get_headers() method
        self.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="}
        )

    @patch("requests.post")
    def test_create_user(self, mock_post):
        """Test create_user function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "user123",
                "user_name": "alice.radiology",
            }
        }
        mock_post.return_value = mock_response

        # Create test params
        params = CreateUserParams(
            user_name="alice.radiology",
            first_name="Alice",
            last_name="Radiology",
            email="alice@example.com",
            department="Radiology",
            title="Doctor",
        )

        # Call function
        result = create_user(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.user_id, "user123")
        self.assertEqual(result.user_name, "alice.radiology")

        # Verify mock was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/sys_user")
        self.assertEqual(call_args[1]["json"]["user_name"], "alice.radiology")
        self.assertEqual(call_args[1]["json"]["first_name"], "Alice")
        self.assertEqual(call_args[1]["json"]["last_name"], "Radiology")
        self.assertEqual(call_args[1]["json"]["email"], "alice@example.com")
        self.assertEqual(call_args[1]["json"]["department"], "Radiology")
        self.assertEqual(call_args[1]["json"]["title"], "Doctor")

    @patch("requests.patch")
    def test_update_user(self, mock_patch):
        """Test update_user function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "user123",
                "user_name": "alice.radiology",
            }
        }
        mock_patch.return_value = mock_response

        # Create test params
        params = UpdateUserParams(
            user_id="user123",
            manager="user456",
            title="Senior Doctor",
        )

        # Call function
        result = update_user(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.user_id, "user123")
        self.assertEqual(result.user_name, "alice.radiology")

        # Verify mock was called correctly
        mock_patch.assert_called_once()
        call_args = mock_patch.call_args
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/sys_user/user123")
        self.assertEqual(call_args[1]["json"]["manager"], "user456")
        self.assertEqual(call_args[1]["json"]["title"], "Senior Doctor")

    @patch("requests.get")
    def test_get_user(self, mock_get):
        """Test get_user function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "user123",
                    "user_name": "alice.radiology",
                    "first_name": "Alice",
                    "last_name": "Radiology",
                    "email": "alice@example.com",
                }
            ]
        }
        mock_get.return_value = mock_response

        # Create test params
        params = GetUserParams(
            user_name="alice.radiology",
        )

        # Call function
        result = get_user(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["user"]["sys_id"], "user123")
        self.assertEqual(result["user"]["user_name"], "alice.radiology")

        # Verify mock was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/sys_user")
        self.assertEqual(call_args[1]["params"]["sysparm_query"], "user_name=alice.radiology")

    @patch("requests.get")
    def test_list_users(self, mock_get):
        """Test list_users function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "user123",
                    "user_name": "alice.radiology",
                },
                {
                    "sys_id": "user456",
                    "user_name": "bob.chiefradiology",
                },
            ]
        }
        mock_get.return_value = mock_response

        # Create test params
        params = ListUsersParams(
            department="Radiology",
            limit=10,
        )

        # Call function
        result = list_users(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["users"]), 2)
        self.assertEqual(result["users"][0]["sys_id"], "user123")
        self.assertEqual(result["users"][1]["sys_id"], "user456")

        # Verify mock was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/sys_user")
        self.assertEqual(call_args[1]["params"]["sysparm_limit"], "10")
        self.assertIn("department=Radiology", call_args[1]["params"]["sysparm_query"])

    @patch("requests.get")
    def test_list_customers(self, mock_get):
        """Test list_customers function."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "company123",
                    "name": "Zava",
                    "u_customerid": "101597",
                },
                {
                    "sys_id": "company456",
                    "name": "Contoso",
                    "u_customerid": "200001",
                },
            ]
        }
        mock_get.return_value = mock_response

        params = ListCustomersParams(
            query="Zava",
            only_sso=True,
            limit=10,
            columns=["country", "city"],
            include_contact_emails=True,
        )

        result = list_customers(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["customers"]), 2)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["customers"][0]["name"], "Zava")
        self.assertIn("u_deputyse.email", result["customers"][0])
        self.assertIn("u_sdm.email", result["customers"][0])
        self.assertIn("u_primarysupportgroup.manager.email", result["customers"][0])
        self.assertEqual(result["customers"][0]["u_deputyse.email"], "")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/core_company")
        self.assertEqual(call_args[1]["params"]["sysparm_limit"], "10")
        self.assertIn("sso_sourceISNOTEMPTY", call_args[1]["params"]["sysparm_query"])
        self.assertIn("nameLIKEZava", call_args[1]["params"]["sysparm_query"])
        self.assertIn("country", call_args[1]["params"]["sysparm_fields"])
        self.assertIn("city", call_args[1]["params"]["sysparm_fields"])
        self.assertNotIn("u_centron_id", call_args[1]["params"]["sysparm_fields"])
        self.assertIn("u_primaryse.name", call_args[1]["params"]["sysparm_fields"])
        self.assertIn("u_primarysupportgroup.name", call_args[1]["params"]["sysparm_fields"])
        self.assertIn("u_1_level_group.name", call_args[1]["params"]["sysparm_fields"])
        self.assertIn("u_primaryse.email", call_args[1]["params"]["sysparm_fields"])
        self.assertIn("u_sdm.email", call_args[1]["params"]["sysparm_fields"])
        self.assertIn("u_deputyse.email", call_args[1]["params"]["sysparm_fields"])
        self.assertIn(
            "u_primarysupportgroup.manager.email", call_args[1]["params"]["sysparm_fields"]
        )

    def test_fix_mojibake_text_umlauts_accents(self):
        """Fix mojibake for umlauts and accented characters."""
        cases = {
            "John BrÃ¤ndle": "John Brändle",
            "RenÃ© Doe": "René Doe",
            "MÃ¼ller": "Müller",
            "ZÃ¼rich": "Zürich",
            "FranÃ§ois": "François",
            # Real mojibake generated by encoding correct UTF-8 as UTF-8
            # then decoding those bytes as Latin-1:
            "DÃ©colletage": "Décolletage",
        }
        # Generate mojibake dynamically for chars that produce non-printable
        # Latin-1 bytes (\x80-\x9f) which can't be written literally in source:

        def _mojibake(s):
            return s.encode("utf-8").decode("latin-1")

        cases.update(
            {
                _mojibake("Österreich"): "Österreich",
                _mojibake("Übercool"): "Übercool",
                _mojibake("Straße"): "Straße",
                _mojibake("Żółw"): "Żółw",
            }
        )
        for mojibaked, expected in cases.items():
            with self.subTest(mojibaked=mojibaked):
                self.assertEqual(_fix_mojibake_text(mojibaked), expected)

    def test_fix_mojibake_text_already_clean(self):
        """Already-correct UTF-8 strings pass through unchanged (idempotent)."""
        cases = [
            "John Brändle",
            "René Doe",
            "Müller",
            "Zürich",
            "François",
            "São Paulo",
            "MÁS",
            "Plain ASCII",
            "",
            "12345",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(_fix_mojibake_text(text), text)

    def test_normalize_text_values_nested(self):
        """Normalize mojibake recursively for nested dict/list payloads."""
        payload = {
            "name": "John BrÃ¤ndle",
            "u_sdm": {"display_value": "RenÃ© Doe"},
            "aliases": ["MÃ¼ller", "Plain ASCII"],
        }

        normalized = _normalize_text_values(payload)

        self.assertEqual(normalized["name"], "John Brändle")
        self.assertEqual(normalized["u_sdm"]["display_value"], "René Doe")
        self.assertEqual(normalized["aliases"][0], "Müller")
        self.assertEqual(normalized["aliases"][1], "Plain ASCII")

    @patch("requests.get")
    def test_list_customers_normalizes_mojibake(self, mock_get):
        """Ensure list_customers returns normalized names/display values."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "company789",
                    "name": "John BrÃ¤ndle GmbH",
                    "u_customerid": "300001",
                    "u_sdm": {"display_value": "RenÃ© Doe"},
                }
            ]
        }
        mock_get.return_value = mock_response

        params = ListCustomersParams(limit=1)
        result = list_customers(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["customers"][0]["name"], "John Brändle GmbH")
        self.assertEqual(result["customers"][0]["u_sdm"]["display_value"], "René Doe")

    @patch("requests.get")
    def test_list_customers_caps_large_limit_and_returns_pagination_metadata(self, mock_get):
        """Large list_customers requests are capped and return navigation metadata."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "company123",
                    "name": "Example Customer One",
                    "u_customerid": "101597",
                }
            ]
            * 200
        }
        mock_get.return_value = mock_response

        params = ListCustomersParams(limit=1000, offset=0)
        result = list_customers(self.config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["requested_limit"], 1000)
        self.assertEqual(result["applied_limit"], 200)
        self.assertTrue(result["truncated"])
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 200)
        self.assertIn("warnings", result)
        self.assertIn("MCP-safe maximum", result["warnings"][0])

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["sysparm_limit"], "200")

    def test_build_customer_query_variants_handles_umlauts_and_ampersand(self):
        """Search variants include common umlaut and '&'/'und' forms."""
        variants = _build_customer_query_variants("Sample & Partners Zuerich")

        self.assertIn("Sample & Partners Zuerich", variants)
        self.assertIn("Sample und Partners Zuerich", variants)
        self.assertIn("Sample & Partners Zürich", variants)

    def test_build_customer_query_variants_converts_zuerich_but_not_neue(self):
        """'Neue Zuercher' should become 'Neue Zürcher' without corrupting 'Neue'."""
        variants = _build_customer_query_variants("Treue Zuercher Gruppe AG")

        self.assertIn("Treue Zuercher Gruppe AG", variants)
        self.assertIn("Treue Zürcher Gruppe AG", variants)
        self.assertNotIn("Treüe Zürcher Gruppe AG", variants)

    def test_build_customer_query_variants_handles_legal_suffix_and_alias(self):
        """Search variants include legal-suffix stripped and parenthetical alias forms."""
        variants = _build_customer_query_variants("Example Industrial GmbH (EIG)")

        self.assertIn("Example Industrial GmbH (EIG)", variants)
        self.assertIn("Example Industrial", variants)
        self.assertIn("EIG", variants)

    @patch("requests.get")
    def test_list_customers_query_uses_variant_expansion(self, mock_get):
        """list_customers should search with expanded variants to improve matches."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [{"sys_id": "companyA", "name": "Example", "u_customerid": "A-1"}]
        }
        mock_get.return_value = mock_response

        params = ListCustomersParams(query="Zuerich", limit=10)
        _ = list_customers(self.config, self.auth_manager, params)

        mock_get.assert_called_once()
        sysparm_query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("nameLIKEZuerich", sysparm_query)
        self.assertIn("nameLIKEZürich", sysparm_query)

    @patch("requests.get")
    def test_list_customers_query_includes_legal_suffix_and_alias_variants(self, mock_get):
        """list_customers should include legal-suffix and alias variants in query."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        params = ListCustomersParams(query="Example Industrial GmbH (EIG)", limit=10)
        _ = list_customers(self.config, self.auth_manager, params)

        mock_get.assert_called_once()
        sysparm_query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("nameLIKEExample Industrial", sysparm_query)
        self.assertIn("nameLIKEEIG", sysparm_query)

    @patch("requests.get")
    def test_list_groups(self, mock_get):
        """Test list_groups function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "group123",
                    "name": "IT Support",
                    "description": "IT support team",
                    "active": "true",
                    "type": "it",
                },
                {
                    "sys_id": "group456",
                    "name": "HR Team",
                    "description": "Human Resources team",
                    "active": "true",
                    "type": "administrative",
                },
            ]
        }
        mock_get.return_value = mock_response

        # Create test params
        params = ListGroupsParams(
            active=True,
            type="it",
            query="support",
            limit=10,
        )

        # Call function
        result = list_groups(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["groups"]), 2)
        self.assertEqual(result["groups"][0]["sys_id"], "group123")
        self.assertEqual(result["groups"][1]["sys_id"], "group456")
        self.assertEqual(result["count"], 2)

        # Verify mock was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/sys_user_group")
        self.assertEqual(call_args[1]["params"]["sysparm_limit"], "10")
        self.assertEqual(call_args[1]["params"]["sysparm_offset"], "0")
        self.assertEqual(call_args[1]["params"]["sysparm_display_value"], "true")
        self.assertIn("active=true", call_args[1]["params"]["sysparm_query"])
        self.assertIn("type=it", call_args[1]["params"]["sysparm_query"])
        self.assertIn("nameLIKE", call_args[1]["params"]["sysparm_query"])
        self.assertIn("descriptionLIKE", call_args[1]["params"]["sysparm_query"])

    @patch("requests.post")
    def test_create_group(self, mock_post):
        """Test create_group function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "group123",
                "name": "Biomedical Engineering",
            }
        }
        mock_post.return_value = mock_response

        # Create test params
        params = CreateGroupParams(
            name="Biomedical Engineering",
            description="Group for biomedical engineering staff",
            manager="user456",
        )

        # Call function
        result = create_group(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.group_id, "group123")
        self.assertEqual(result.group_name, "Biomedical Engineering")

        # Verify mock was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/sys_user_group")
        self.assertEqual(call_args[1]["json"]["name"], "Biomedical Engineering")
        self.assertEqual(
            call_args[1]["json"]["description"], "Group for biomedical engineering staff"
        )
        self.assertEqual(call_args[1]["json"]["manager"], "user456")

    @patch("requests.patch")
    def test_update_group(self, mock_patch):
        """Test update_group function."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "group123",
                "name": "Biomedical Engineering",
            }
        }
        mock_patch.return_value = mock_response

        # Create test params
        params = UpdateGroupParams(
            group_id="group123",
            description="Updated description for biomedical engineering group",
            manager="user789",
        )

        # Call function
        result = update_group(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.group_id, "group123")
        self.assertEqual(result.group_name, "Biomedical Engineering")

        # Verify mock was called correctly
        mock_patch.assert_called_once()
        call_args = mock_patch.call_args
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/sys_user_group/group123")
        self.assertEqual(
            call_args[1]["json"]["description"],
            "Updated description for biomedical engineering group",
        )
        self.assertEqual(call_args[1]["json"]["manager"], "user789")

    @patch("servicenow_mcp.tools.user_tools.get_user")
    @patch("requests.post")
    def test_add_group_members(self, mock_post, mock_get_user):
        """Test add_group_members function."""
        # Configure mocks
        mock_post_response = MagicMock()
        mock_post_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_post_response

        mock_get_user.return_value = {
            "success": True,
            "message": "User found",
            "user": {
                "sys_id": "user123",
                "user_name": "alice.radiology",
            },
        }

        # Create test params
        params = AddGroupMembersParams(
            group_id="group123",
            members=["alice.radiology", "admin"],
        )

        # Call function
        result = add_group_members(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.group_id, "group123")

        # Verify mock was called correctly
        self.assertEqual(mock_post.call_count, 2)  # Once for each member
        call_args = mock_post.call_args_list[0]
        self.assertEqual(call_args[0][0], f"{self.config.api_url}/table/sys_user_grmember")
        self.assertEqual(call_args[1]["json"]["group"], "group123")
        self.assertEqual(call_args[1]["json"]["user"], "user123")

    @patch("servicenow_mcp.tools.user_tools.get_user")
    @patch("requests.get")
    @patch("requests.delete")
    def test_remove_group_members(self, mock_delete, mock_get, mock_get_user):
        """Test remove_group_members function."""
        # Configure mocks
        mock_delete_response = MagicMock()
        mock_delete_response.raise_for_status = MagicMock()
        mock_delete.return_value = mock_delete_response

        mock_get_response = MagicMock()
        mock_get_response.raise_for_status = MagicMock()
        mock_get_response.json.return_value = {
            "result": [
                {
                    "sys_id": "member123",
                    "user": {
                        "value": "user123",
                        "display_value": "Alice Radiology",
                    },
                    "group": {
                        "value": "group123",
                        "display_value": "Biomedical Engineering",
                    },
                }
            ]
        }
        mock_get.return_value = mock_get_response

        mock_get_user.return_value = {
            "success": True,
            "message": "User found",
            "user": {
                "sys_id": "user123",
                "user_name": "alice.radiology",
            },
        }

        # Create test params
        params = RemoveGroupMembersParams(
            group_id="group123",
            members=["alice.radiology"],
        )

        # Call function
        result = remove_group_members(self.config, self.auth_manager, params)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.group_id, "group123")

        # Verify mock was called correctly
        mock_get.assert_called_once()
        get_call_args = mock_get.call_args
        self.assertEqual(get_call_args[0][0], f"{self.config.api_url}/table/sys_user_grmember")
        self.assertEqual(get_call_args[1]["params"]["sysparm_query"], "group=group123^user=user123")

        mock_delete.assert_called_once()
        delete_call_args = mock_delete.call_args
        self.assertEqual(
            delete_call_args[0][0], f"{self.config.api_url}/table/sys_user_grmember/member123"
        )


if __name__ == "__main__":
    unittest.main()
