"""
Tests for the knowledge base tools.

This module contains tests for the knowledge base tools in the ServiceNow MCP server.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.knowledge_base import (
    CreateArticleParams,
    CreateCategoryParams,
    CreateKnowledgeBaseParams,
    GetArticleParams,
    ListArticlesParams,
    ListKnowledgeBasesParams,
    PublishArticleParams,
    UpdateArticleParams,
    ListCategoriesParams,
    create_article,
    create_category,
    create_knowledge_base,
    get_article,
    list_articles,
    list_knowledge_bases,
    publish_article,
    update_article,
    list_categories,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestKnowledgeBaseTools(unittest.TestCase):
    """Tests for the knowledge base tools."""

    def setUp(self):
        """Set up test fixtures."""
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.server_config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {
            "Authorization": "Bearer test",
            "Content-Type": "application/json",
        }

    @patch("servicenow_mcp.tools.knowledge_base.requests.post")
    def test_create_knowledge_base(self, mock_post):
        """Test creating a knowledge base."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "kb001",
                "title": "Test Knowledge Base",
                "description": "Test Description",
                "owner": "admin",
                "kb_managers": "it_managers",
                "workflow_publish": "Knowledge - Instant Publish",
                "workflow_retire": "Knowledge - Instant Retire",
            }
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Call the method
        params = CreateKnowledgeBaseParams(
            title="Test Knowledge Base",
            description="Test Description",
            owner="admin",
            managers="it_managers",
        )
        result = create_knowledge_base(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result.success)
        self.assertEqual("kb001", result.kb_id)
        self.assertEqual("Test Knowledge Base", result.kb_name)

        # Verify the request
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_knowledge_base", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual("Test Knowledge Base", kwargs["json"]["title"])
        self.assertEqual("Test Description", kwargs["json"]["description"])
        self.assertEqual("admin", kwargs["json"]["owner"])
        self.assertEqual("it_managers", kwargs["json"]["kb_managers"])

    @patch("servicenow_mcp.tools.knowledge_base.requests.post")
    def test_create_category(self, mock_post):
        """Test creating a category."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "cat001",
                "label": "Test Category",
                "description": "Test Category Description",
                "kb_knowledge_base": "kb001",
                "parent": "",
                "active": "true",
            }
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Call the method
        params = CreateCategoryParams(
            title="Test Category",
            description="Test Category Description",
            knowledge_base="kb001",
            active=True,
        )
        result = create_category(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result.success)
        self.assertEqual("cat001", result.category_id)
        self.assertEqual("Test Category", result.category_name)

        # Verify the request
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_category", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual("Test Category", kwargs["json"]["label"])
        self.assertEqual("Test Category Description", kwargs["json"]["description"])
        self.assertEqual("kb001", kwargs["json"]["kb_knowledge_base"])
        self.assertEqual("true", kwargs["json"]["active"])

    @patch("servicenow_mcp.tools.knowledge_base.requests.post")
    def test_create_article(self, mock_post):
        """Test creating a knowledge article."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "art001",
                "short_description": "Test Article",
                "text": "This is a test article content",
                "kb_knowledge_base": "kb001",
                "kb_category": "cat001",
                "article_type": "text",
                "keywords": "test,article,knowledge",
                "workflow_state": "draft",
            }
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Call the method
        params = CreateArticleParams(
            title="Test Article",
            short_description="Test Article",
            text="This is a test article content",
            knowledge_base="kb001",
            category="cat001",
            keywords="test,article,knowledge",
            article_type="text",
        )
        result = create_article(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result.success)
        self.assertEqual("art001", result.article_id)
        self.assertEqual("Test Article", result.article_title)

        # Verify the request
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_knowledge", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual("Test Article", kwargs["json"]["short_description"])
        self.assertEqual("This is a test article content", kwargs["json"]["text"])
        self.assertEqual("kb001", kwargs["json"]["kb_knowledge_base"])
        self.assertEqual("cat001", kwargs["json"]["kb_category"])
        self.assertEqual("text", kwargs["json"]["article_type"])
        self.assertEqual("test,article,knowledge", kwargs["json"]["keywords"])

    @patch("servicenow_mcp.tools.knowledge_base.requests.patch")
    def test_update_article(self, mock_patch):
        """Test updating a knowledge article."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "art001",
                "short_description": "Updated Article",
                "text": "This is an updated article content",
                "kb_category": "cat002",
                "keywords": "updated,article,knowledge",
                "workflow_state": "draft",
            }
        }
        mock_response.status_code = 200
        mock_patch.return_value = mock_response

        # Call the method
        params = UpdateArticleParams(
            article_id="art001",
            title="Updated Article",
            text="This is an updated article content",
            category="cat002",
            keywords="updated,article,knowledge",
        )
        result = update_article(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result.success)
        self.assertEqual("art001", result.article_id)
        self.assertEqual("Updated Article", result.article_title)

        # Verify the request
        mock_patch.assert_called_once()
        args, kwargs = mock_patch.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_knowledge/art001", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual("Updated Article", kwargs["json"]["short_description"])
        self.assertEqual("This is an updated article content", kwargs["json"]["text"])
        self.assertEqual("cat002", kwargs["json"]["kb_category"])
        self.assertEqual("updated,article,knowledge", kwargs["json"]["keywords"])

    @patch("servicenow_mcp.tools.knowledge_base.requests.patch")
    def test_publish_article(self, mock_patch):
        """Test publishing a knowledge article."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "art001",
                "short_description": "Test Article",
                "workflow_state": "published",
            }
        }
        mock_response.status_code = 200
        mock_patch.return_value = mock_response

        # Call the method
        params = PublishArticleParams(article_id="art001", workflow_state="published")
        result = publish_article(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result.success)
        self.assertEqual("art001", result.article_id)
        self.assertEqual("Test Article", result.article_title)
        self.assertEqual("published", result.workflow_state)

        # Verify the request
        mock_patch.assert_called_once()
        args, kwargs = mock_patch.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_knowledge/art001", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual("published", kwargs["json"]["workflow_state"])

    @patch("servicenow_mcp.tools.knowledge_base.requests.get")
    def test_list_articles(self, mock_get):
        """Test listing knowledge articles."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "art001",
                    "short_description": "Test Article 1",
                    "kb_knowledge_base": {"display_value": "IT Knowledge Base"},
                    "kb_category": {"display_value": "Network"},
                    "workflow_state": {"display_value": "Published"},
                    "sys_created_on": "2023-01-01 00:00:00",
                    "sys_updated_on": "2023-01-02 00:00:00",
                },
                {
                    "sys_id": "art002",
                    "short_description": "Test Article 2",
                    "kb_knowledge_base": {"display_value": "IT Knowledge Base"},
                    "kb_category": {"display_value": "Software"},
                    "workflow_state": {"display_value": "Draft"},
                    "sys_created_on": "2023-01-03 00:00:00",
                    "sys_updated_on": "2023-01-04 00:00:00",
                },
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Call the method
        params = ListArticlesParams(
            limit=10,
            offset=0,
            knowledge_base="kb001",
            category="cat001",
            workflow_state="published",
            query="network",
        )
        result = list_articles(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(2, len(result["articles"]))
        self.assertEqual("art001", result["articles"][0]["id"])
        self.assertEqual("Test Article 1", result["articles"][0]["title"])
        self.assertEqual("IT Knowledge Base", result["articles"][0]["knowledge_base"])
        self.assertEqual("Network", result["articles"][0]["category"])
        self.assertEqual("Published", result["articles"][0]["workflow_state"])

        # Verify the request
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_knowledge", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual(10, kwargs["params"]["sysparm_limit"])
        self.assertEqual(0, kwargs["params"]["sysparm_offset"])
        self.assertEqual("all", kwargs["params"]["sysparm_display_value"])

        # Verify the query syntax contains the correct pattern
        self.assertIn("sysparm_query", kwargs["params"])
        query = kwargs["params"]["sysparm_query"]
        self.assertIn("kb_knowledge_base.sys_id=kb001", query)
        self.assertIn("kb_category.sys_id=cat001", query)

    @patch("servicenow_mcp.tools.knowledge_base.requests.get")
    def test_get_article(self, mock_get):
        """Test getting a knowledge article."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "art001",
                "short_description": "Test Article",
                "text": "This is a test article content",
                "kb_knowledge_base": {"display_value": "IT Knowledge Base"},
                "kb_category": {"display_value": "Network"},
                "workflow_state": {"display_value": "Published"},
                "sys_created_on": "2023-01-01 00:00:00",
                "sys_updated_on": "2023-01-02 00:00:00",
                "author": {"display_value": "admin"},
                "keywords": "test,article,knowledge",
                "article_type": "text",
                "view_count": "42",
            }
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Call the method
        params = GetArticleParams(article_id="art001")
        result = get_article(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual("art001", result["article"]["id"])
        self.assertEqual("Test Article", result["article"]["title"])
        self.assertEqual("This is a test article content", result["article"]["text"])
        self.assertEqual("IT Knowledge Base", result["article"]["knowledge_base"])
        self.assertEqual("Network", result["article"]["category"])
        self.assertEqual("Published", result["article"]["workflow_state"])
        self.assertEqual("admin", result["article"]["author"])
        self.assertEqual("test,article,knowledge", result["article"]["keywords"])
        self.assertEqual("text", result["article"]["article_type"])
        self.assertEqual("42", result["article"]["views"])

        # Verify the request
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_knowledge/art001", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual("true", kwargs["params"]["sysparm_display_value"])

    @patch("servicenow_mcp.tools.knowledge_base.requests.post")
    def test_create_knowledge_base_error(self, mock_post):
        """Test error handling when creating a knowledge base."""
        # Mock error response
        mock_post.side_effect = requests.RequestException("API error")

        # Call the method
        params = CreateKnowledgeBaseParams(title="Test Knowledge Base")
        result = create_knowledge_base(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertFalse(result.success)
        self.assertIn("Failed to create knowledge base", result.message)

    @patch("servicenow_mcp.tools.knowledge_base.requests.get")
    def test_get_article_not_found(self, mock_get):
        """Test getting a non-existent article."""
        # Mock empty response
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {}}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Call the method
        params = GetArticleParams(article_id="nonexistent")
        result = get_article(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.knowledge_base.requests.get")
    def test_list_knowledge_bases(self, mock_get):
        """Test listing knowledge bases."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "kb001",
                    "title": "IT Knowledge Base",
                    "description": "Knowledge base for IT resources",
                    "owner": {"display_value": "admin"},
                    "kb_managers": {"display_value": "it_managers"},
                    "active": "true",
                    "sys_created_on": "2023-01-01 00:00:00",
                    "sys_updated_on": "2023-01-02 00:00:00",
                },
                {
                    "sys_id": "kb002",
                    "title": "HR Knowledge Base",
                    "description": "Knowledge base for HR resources",
                    "owner": {"display_value": "hr_admin"},
                    "kb_managers": {"display_value": "hr_managers"},
                    "active": "true",
                    "sys_created_on": "2023-01-03 00:00:00",
                    "sys_updated_on": "2023-01-04 00:00:00",
                },
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Call the method
        params = ListKnowledgeBasesParams(limit=10, offset=0, active=True, query="IT")
        result = list_knowledge_bases(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(2, len(result["knowledge_bases"]))
        self.assertEqual("kb001", result["knowledge_bases"][0]["id"])
        self.assertEqual("IT Knowledge Base", result["knowledge_bases"][0]["title"])
        self.assertEqual(
            "Knowledge base for IT resources", result["knowledge_bases"][0]["description"]
        )
        self.assertEqual("admin", result["knowledge_bases"][0]["owner"])
        self.assertEqual("it_managers", result["knowledge_bases"][0]["managers"])
        self.assertTrue(result["knowledge_bases"][0]["active"])

        # Verify the request
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_knowledge_base", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual(10, kwargs["params"]["sysparm_limit"])
        self.assertEqual(0, kwargs["params"]["sysparm_offset"])
        self.assertEqual("true", kwargs["params"]["sysparm_display_value"])
        self.assertEqual(
            "active=true^titleLIKEIT^ORdescriptionLIKEIT", kwargs["params"]["sysparm_query"]
        )

    @patch("servicenow_mcp.tools.knowledge_base.requests.get")
    def test_list_categories(self, mock_get):
        """Test listing categories in a knowledge base."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "sys_id": "cat001",
                    "label": "Network Troubleshooting",
                    "description": "Articles for network troubleshooting",
                    "kb_knowledge_base": {"display_value": "IT Knowledge Base"},
                    "parent": {"display_value": ""},
                    "active": "true",
                    "sys_created_on": "2023-01-01 00:00:00",
                    "sys_updated_on": "2023-01-02 00:00:00",
                },
                {
                    "sys_id": "cat002",
                    "label": "Software Setup",
                    "description": "Articles for software installation",
                    "kb_knowledge_base": {"display_value": "IT Knowledge Base"},
                    "parent": {"display_value": ""},
                    "active": "true",
                    "sys_created_on": "2023-01-03 00:00:00",
                    "sys_updated_on": "2023-01-04 00:00:00",
                },
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Call the method
        params = ListCategoriesParams(knowledge_base="kb001", active=True, query="Network")
        result = list_categories(self.server_config, self.auth_manager, params)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(2, len(result["categories"]))
        self.assertEqual("cat001", result["categories"][0]["id"])
        self.assertEqual("Network Troubleshooting", result["categories"][0]["title"])
        self.assertEqual(
            "Articles for network troubleshooting", result["categories"][0]["description"]
        )
        self.assertEqual("IT Knowledge Base", result["categories"][0]["knowledge_base"])
        self.assertEqual("", result["categories"][0]["parent_category"])
        self.assertTrue(result["categories"][0]["active"])

        # Verify the request
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(f"{self.server_config.api_url}/table/kb_category", args[0])
        self.assertEqual(self.auth_manager.get_headers(), kwargs["headers"])
        self.assertEqual(10, kwargs["params"]["sysparm_limit"])
        self.assertEqual(0, kwargs["params"]["sysparm_offset"])
        self.assertEqual("all", kwargs["params"]["sysparm_display_value"])

        # Verify the query syntax contains the correct pattern
        self.assertIn("sysparm_query", kwargs["params"])
        query = kwargs["params"]["sysparm_query"]
        self.assertIn("kb_knowledge_base.sys_id=kb001", query)
        self.assertIn("active=true", query)
        self.assertIn("labelLIKENetwork", query)


class TestKnowledgeBaseParams(unittest.TestCase):
    """Tests for the knowledge base parameter classes."""

    def test_create_knowledge_base_params(self):
        """Test CreateKnowledgeBaseParams validation."""
        # Minimal required parameters
        params = CreateKnowledgeBaseParams(title="Test Knowledge Base")
        self.assertEqual("Test Knowledge Base", params.title)
        self.assertEqual("Knowledge - Instant Publish", params.publish_workflow)

        # All parameters
        params = CreateKnowledgeBaseParams(
            title="Test Knowledge Base",
            description="Test Description",
            owner="admin",
            managers="it_managers",
            publish_workflow="Custom Workflow",
            retire_workflow="Custom Retire Workflow",
        )
        self.assertEqual("Test Knowledge Base", params.title)
        self.assertEqual("Test Description", params.description)
        self.assertEqual("admin", params.owner)
        self.assertEqual("it_managers", params.managers)
        self.assertEqual("Custom Workflow", params.publish_workflow)
        self.assertEqual("Custom Retire Workflow", params.retire_workflow)

    def test_create_category_params(self):
        """Test CreateCategoryParams validation."""
        # Required parameters
        params = CreateCategoryParams(title="Test Category", knowledge_base="kb001")
        self.assertEqual("Test Category", params.title)
        self.assertEqual("kb001", params.knowledge_base)
        self.assertTrue(params.active)

        # All parameters
        params = CreateCategoryParams(
            title="Test Category",
            description="Test Description",
            knowledge_base="kb001",
            parent_category="parent001",
            active=False,
        )
        self.assertEqual("Test Category", params.title)
        self.assertEqual("Test Description", params.description)
        self.assertEqual("kb001", params.knowledge_base)
        self.assertEqual("parent001", params.parent_category)
        self.assertFalse(params.active)

    def test_create_article_params(self):
        """Test CreateArticleParams validation."""
        # Required parameters
        params = CreateArticleParams(
            title="Test Article",
            text="Test content",
            short_description="Test short description",
            knowledge_base="kb001",
            category="cat001",
        )
        self.assertEqual("Test Article", params.title)
        self.assertEqual("Test content", params.text)
        self.assertEqual("Test short description", params.short_description)
        self.assertEqual("kb001", params.knowledge_base)
        self.assertEqual("cat001", params.category)
        self.assertEqual("text", params.article_type)

        # All parameters
        params = CreateArticleParams(
            title="Test Article",
            text="Test content",
            short_description="Test short description",
            knowledge_base="kb001",
            category="cat001",
            keywords="test,article",
            article_type="html",
        )
        self.assertEqual("Test Article", params.title)
        self.assertEqual("Test content", params.text)
        self.assertEqual("Test short description", params.short_description)
        self.assertEqual("kb001", params.knowledge_base)
        self.assertEqual("cat001", params.category)
        self.assertEqual("test,article", params.keywords)
        self.assertEqual("html", params.article_type)


class TestListArticlesByCategory(unittest.TestCase):
    """Tests for list_articles_by_category tool."""

    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.server_config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {
            "Authorization": "Bearer test",
            "Content-Type": "application/json",
        }

    def _make_category_response(self, sys_id="cat001", label="How-To"):
        mock = MagicMock()
        mock.json.return_value = {"result": [{"sys_id": sys_id, "label": label}]}
        mock.raise_for_status = MagicMock()
        return mock

    def _make_articles_response(self, articles):
        mock = MagicMock()
        mock.json.return_value = {"result": articles}
        mock.raise_for_status = MagicMock()
        return mock

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_list_by_category_name_resolves_to_sys_id(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        mock_req.side_effect = [
            self._make_category_response(sys_id="cat001", label="How-To"),
            self._make_articles_response(
                [
                    {
                        "sys_id": "art001",
                        "short_description": {"display_value": "Reset password"},
                        "kb_knowledge_base": {"display_value": "IT KB"},
                        "kb_category": {"display_value": "How-To"},
                        "workflow_state": {"display_value": "published"},
                        "author": {"display_value": "admin"},
                        "keywords": {"display_value": "password,reset"},
                        "view_count": {"display_value": "42"},
                        "article_type": {"display_value": "html"},
                        "sys_created_on": "2024-01-01 00:00:00",
                        "sys_updated_on": "2024-06-01 00:00:00",
                    }
                ]
            ),
        ]

        params = ListArticlesByCategoryParams(category="How-To")
        result = list_articles_by_category(self.server_config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(1, result["count"])
        self.assertEqual("art001", result["articles"][0]["id"])
        self.assertEqual("Reset password", result["articles"][0]["title"])
        self.assertEqual("cat001", result["category_sys_id"])
        # Body should NOT be present unless include_body=True
        self.assertNotIn("text", result["articles"][0])

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_list_by_category_sys_id_skips_lookup(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        # 32-char hex sys_id should skip the category lookup GET
        cat_sys_id = "a" * 32
        mock_req.return_value = self._make_articles_response([])

        params = ListArticlesByCategoryParams(category=cat_sys_id)
        result = list_articles_by_category(self.server_config, self.auth_manager, params)

        self.assertTrue(result["success"])
        # Only one request should have been made (no category lookup)
        self.assertEqual(1, mock_req.call_count)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_category_not_found_returns_error(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        # Category lookup returns empty list
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        params = ListArticlesByCategoryParams(category="Nonexistent Category")
        result = list_articles_by_category(self.server_config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertEqual([], result["articles"])

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_include_body_adds_text_field(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        mock_req.side_effect = [
            self._make_category_response(),
            self._make_articles_response(
                [
                    {
                        "sys_id": "art002",
                        "short_description": {"display_value": "VPN Setup"},
                        "kb_knowledge_base": {"display_value": "IT KB"},
                        "kb_category": {"display_value": "How-To"},
                        "workflow_state": {"display_value": "published"},
                        "author": {"display_value": "admin"},
                        "keywords": {"display_value": "vpn"},
                        "view_count": {"display_value": "10"},
                        "article_type": {"display_value": "html"},
                        "text": {"display_value": "<p>Steps to set up VPN</p>"},
                        "sys_created_on": "2024-01-01 00:00:00",
                        "sys_updated_on": "2024-06-01 00:00:00",
                    }
                ]
            ),
        ]

        params = ListArticlesByCategoryParams(category="How-To", include_body=True)
        result = list_articles_by_category(self.server_config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertIn("text", result["articles"][0])
        self.assertEqual("<p>Steps to set up VPN</p>", result["articles"][0]["text"])

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_workflow_state_filter_applied(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        mock_req.side_effect = [
            self._make_category_response(),
            self._make_articles_response([]),
        ]

        params = ListArticlesByCategoryParams(category="How-To", workflow_state="published")
        list_articles_by_category(self.server_config, self.auth_manager, params)

        # Second call is the articles request; verify query contains state filter
        articles_call = mock_req.call_args_list[1]
        query = articles_call[1]["params"]["sysparm_query"]
        self.assertIn("workflow_state=published", query)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_http_error_on_articles_request(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        mock_req.side_effect = [
            self._make_category_response(),
            requests.RequestException("503 Service Unavailable"),
        ]

        params = ListArticlesByCategoryParams(category="How-To")
        result = list_articles_by_category(self.server_config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("Failed to list articles", result["message"])

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_category_lookup_with_knowledge_base_filter(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        mock_req.side_effect = [
            self._make_category_response(),
            self._make_articles_response([]),
        ]

        params = ListArticlesByCategoryParams(category="How-To", knowledge_base="IT Knowledge Base")
        list_articles_by_category(self.server_config, self.auth_manager, params)

        # First call is the category lookup; verify it includes KB filter
        cat_call = mock_req.call_args_list[0]
        query = cat_call[1]["params"]["sysparm_query"]
        self.assertIn("kb_knowledge_base.titleLIKE", query)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_category_lookup_with_kb_sys_id(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        mock_req.side_effect = [
            self._make_category_response(),
            self._make_articles_response([]),
        ]

        kb_sys_id = "b" * 32
        params = ListArticlesByCategoryParams(category="How-To", knowledge_base=kb_sys_id)
        list_articles_by_category(self.server_config, self.auth_manager, params)

        cat_call = mock_req.call_args_list[0]
        query = cat_call[1]["params"]["sysparm_query"]
        self.assertIn(f"kb_knowledge_base={kb_sys_id}", query)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_unexpected_response_format(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        cat_sys_id = "c" * 32
        # Articles request returns malformed response
        bad_resp = MagicMock()
        bad_resp.json.return_value = "not a dict"
        bad_resp.raise_for_status = MagicMock()
        mock_req.return_value = bad_resp

        params = ListArticlesByCategoryParams(category=cat_sys_id)
        result = list_articles_by_category(self.server_config, self.auth_manager, params)

        self.assertFalse(result["success"])
        self.assertIn("Unexpected response format", result["message"])

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_pagination_metadata(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            ListArticlesByCategoryParams,
            list_articles_by_category,
        )

        articles = [
            {
                "sys_id": f"art{i:03d}",
                "short_description": {"display_value": f"Article {i}"},
                "kb_knowledge_base": {"display_value": "IT KB"},
                "kb_category": {"display_value": "How-To"},
                "workflow_state": {"display_value": "published"},
                "author": {"display_value": "admin"},
                "keywords": {"display_value": ""},
                "view_count": {"display_value": str(i)},
                "article_type": {"display_value": "html"},
                "sys_created_on": "2024-01-01 00:00:00",
                "sys_updated_on": "2024-06-01 00:00:00",
            }
            for i in range(5)
        ]
        mock_req.side_effect = [
            self._make_category_response(),
            self._make_articles_response(articles),
        ]

        params = ListArticlesByCategoryParams(category="How-To", limit=5, offset=10)
        result = list_articles_by_category(self.server_config, self.auth_manager, params)

        self.assertTrue(result["success"])
        self.assertEqual(5, result["count"])
        self.assertEqual(5, result["limit"])
        self.assertEqual(10, result["offset"])


class TestCreateKnowledgeArticle(unittest.TestCase):
    """Tests for create_knowledge_article tool."""

    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test_user", password="test_password"),
        )
        self.server_config = ServerConfig(
            instance_url="https://test.service-now.com",
            auth=auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer test"}

    def _kb_response(self, sys_id="kb001"):
        m = MagicMock()
        m.json.return_value = {"result": [{"sys_id": sys_id, "title": "IT KB"}]}
        m.raise_for_status = MagicMock()
        return m

    def _cat_response(self, sys_id="cat001"):
        m = MagicMock()
        m.json.return_value = {"result": [{"sys_id": sys_id, "label": "How-To"}]}
        m.raise_for_status = MagicMock()
        return m

    def _article_response(self, sys_id="art001", title="My Article", state="draft"):
        m = MagicMock()
        m.json.return_value = {
            "result": {
                "sys_id": sys_id,
                "short_description": title,
                "workflow_state": state,
            }
        }
        m.raise_for_status = MagicMock()
        return m

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_create_with_names_resolves_and_posts(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        mock_req.side_effect = [
            self._kb_response("kb001"),
            self._cat_response("cat001"),
            self._article_response("art001", "My Article"),
        ]

        params = CreateKnowledgeArticleParams(
            title="My Article",
            text="<p>Body text</p>",
            knowledge_base="IT KB",
            category="How-To",
        )
        result = create_knowledge_article(self.server_config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual("art001", result.article_id)
        self.assertEqual("My Article", result.article_title)
        self.assertEqual("draft", result.workflow_state)
        self.assertEqual(3, mock_req.call_count)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_kb_sys_id_skips_kb_lookup(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        kb_sys_id = "a" * 32
        mock_req.side_effect = [
            self._cat_response("cat001"),
            self._article_response(),
        ]

        params = CreateKnowledgeArticleParams(
            title="Article",
            text="Body",
            knowledge_base=kb_sys_id,
            category="How-To",
        )
        result = create_knowledge_article(self.server_config, self.auth_manager, params)

        self.assertTrue(result.success)
        # Only 2 calls: category lookup + POST
        self.assertEqual(2, mock_req.call_count)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_both_sys_ids_skips_both_lookups(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        kb_sys_id = "a" * 32
        cat_sys_id = "b" * 32
        mock_req.return_value = self._article_response()

        params = CreateKnowledgeArticleParams(
            title="Article",
            text="Body",
            knowledge_base=kb_sys_id,
            category=cat_sys_id,
        )
        result = create_knowledge_article(self.server_config, self.auth_manager, params)

        self.assertTrue(result.success)
        # Only 1 call: the POST
        self.assertEqual(1, mock_req.call_count)
        post_call = mock_req.call_args
        self.assertEqual("POST", post_call[0][0])

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_optional_fields_sent_in_body(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        kb_sys_id = "a" * 32
        cat_sys_id = "b" * 32
        mock_req.return_value = self._article_response()

        params = CreateKnowledgeArticleParams(
            title="Article",
            text="Body",
            knowledge_base=kb_sys_id,
            category=cat_sys_id,
            keywords="tag1,tag2",
            author="user001",
            valid_to="2026-12-31",
            flagged=True,
            disable_commenting=True,
            disable_suggesting=False,
        )
        create_knowledge_article(self.server_config, self.auth_manager, params)

        body = mock_req.call_args[1]["json"]
        self.assertEqual("tag1,tag2", body["keywords"])
        self.assertEqual("user001", body["author"])
        self.assertEqual("2026-12-31", body["valid_to"])
        self.assertEqual("true", body["flagged"])
        self.assertEqual("true", body["disable_commenting"])
        self.assertEqual("false", body["disable_suggesting"])

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_publish_flag_sets_workflow_state(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        kb_sys_id = "a" * 32
        cat_sys_id = "b" * 32
        mock_req.return_value = self._article_response(state="published")

        params = CreateKnowledgeArticleParams(
            title="Article",
            text="Body",
            knowledge_base=kb_sys_id,
            category=cat_sys_id,
            publish=True,
        )
        result = create_knowledge_article(self.server_config, self.auth_manager, params)

        self.assertTrue(result.success)
        body = mock_req.call_args[1]["json"]
        self.assertEqual("published", body["workflow_state"])

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_kb_not_found_returns_failure(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        not_found = MagicMock()
        not_found.json.return_value = {"result": []}
        not_found.raise_for_status = MagicMock()
        mock_req.return_value = not_found

        params = CreateKnowledgeArticleParams(
            title="Article",
            text="Body",
            knowledge_base="Nonexistent KB",
            category="How-To",
        )
        result = create_knowledge_article(self.server_config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Nonexistent KB", result.message)
        self.assertIn("not found", result.message)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_category_not_found_returns_failure(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        kb_sys_id = "a" * 32
        not_found = MagicMock()
        not_found.json.return_value = {"result": []}
        not_found.raise_for_status = MagicMock()
        mock_req.return_value = not_found

        params = CreateKnowledgeArticleParams(
            title="Article",
            text="Body",
            knowledge_base=kb_sys_id,
            category="Bad Category",
        )
        result = create_knowledge_article(self.server_config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Bad Category", result.message)
        self.assertIn("not found", result.message)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_http_error_on_post(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        kb_sys_id = "a" * 32
        cat_sys_id = "b" * 32
        mock_req.side_effect = requests.RequestException("500 Server Error")

        params = CreateKnowledgeArticleParams(
            title="Article",
            text="Body",
            knowledge_base=kb_sys_id,
            category=cat_sys_id,
        )
        result = create_knowledge_article(self.server_config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to create knowledge article", result.message)

    @patch("servicenow_mcp.tools.knowledge_base._make_request")
    def test_correct_fields_in_post_body(self, mock_req):
        from servicenow_mcp.tools.knowledge_base import (
            CreateKnowledgeArticleParams,
            create_knowledge_article,
        )

        kb_sys_id = "a" * 32
        cat_sys_id = "b" * 32
        mock_req.return_value = self._article_response()

        params = CreateKnowledgeArticleParams(
            title="My Title",
            text="<p>Content</p>",
            knowledge_base=kb_sys_id,
            category=cat_sys_id,
            article_type="wiki",
        )
        create_knowledge_article(self.server_config, self.auth_manager, params)

        body = mock_req.call_args[1]["json"]
        self.assertEqual("My Title", body["short_description"])
        self.assertEqual("<p>Content</p>", body["text"])
        self.assertEqual(kb_sys_id, body["kb_knowledge_base"])
        self.assertEqual(cat_sys_id, body["kb_category"])
        self.assertEqual("wiki", body["article_type"])
        self.assertNotIn("workflow_state", body)

    def test_params_defaults(self):
        from servicenow_mcp.tools.knowledge_base import CreateKnowledgeArticleParams

        params = CreateKnowledgeArticleParams(
            title="T", text="B", knowledge_base="kb", category="cat"
        )
        self.assertEqual("html", params.article_type)
        self.assertFalse(params.publish)
        self.assertIsNone(params.author)
        self.assertIsNone(params.valid_to)
        self.assertIsNone(params.flagged)
        self.assertIsNone(params.disable_commenting)
        self.assertIsNone(params.disable_suggesting)


if __name__ == "__main__":
    unittest.main()
