"""Tests for the pagination helper functions in servicenow_mcp.utils.helpers."""


from servicenow_mcp.utils.helpers import (
    _build_sysparm_params,
    _join_query_parts,
    _paginated_list_response,
)


# ---------------------------------------------------------------------------
# _build_sysparm_params
# ---------------------------------------------------------------------------


class TestBuildSysparmParams:
    def test_minimal_returns_required_keys(self):
        p = _build_sysparm_params(10, 0)
        assert p["sysparm_limit"] == 10
        assert p["sysparm_offset"] == 0
        assert p["sysparm_display_value"] == "true"

    def test_minimal_no_optional_keys(self):
        p = _build_sysparm_params(10, 0)
        assert "sysparm_query" not in p
        assert "sysparm_exclude_reference_link" not in p
        assert "sysparm_orderby" not in p
        assert "sysparm_fields" not in p

    def test_nonzero_offset(self):
        p = _build_sysparm_params(20, 40)
        assert p["sysparm_limit"] == 20
        assert p["sysparm_offset"] == 40

    def test_query_included_when_provided(self):
        p = _build_sysparm_params(10, 0, query="state=1^priority=2")
        assert p["sysparm_query"] == "state=1^priority=2"

    def test_empty_query_not_included(self):
        p = _build_sysparm_params(10, 0, query="")
        assert "sysparm_query" not in p

    def test_none_query_not_included(self):
        p = _build_sysparm_params(10, 0, query=None)
        assert "sysparm_query" not in p

    def test_exclude_reference_link_true(self):
        p = _build_sysparm_params(10, 0, exclude_reference_link=True)
        assert p["sysparm_exclude_reference_link"] == "true"

    def test_exclude_reference_link_false_not_in_dict(self):
        p = _build_sysparm_params(10, 0, exclude_reference_link=False)
        assert "sysparm_exclude_reference_link" not in p

    def test_order_by_included(self):
        p = _build_sysparm_params(10, 0, order_by="DESCsys_created_on")
        assert p["sysparm_orderby"] == "DESCsys_created_on"

    def test_order_by_none_not_included(self):
        p = _build_sysparm_params(10, 0, order_by=None)
        assert "sysparm_orderby" not in p

    def test_fields_included(self):
        p = _build_sysparm_params(10, 0, fields="sys_id,level,message")
        assert p["sysparm_fields"] == "sys_id,level,message"

    def test_fields_none_not_included(self):
        p = _build_sysparm_params(10, 0, fields=None)
        assert "sysparm_fields" not in p

    def test_custom_display_value(self):
        p = _build_sysparm_params(10, 0, display_value="all")
        assert p["sysparm_display_value"] == "all"

    def test_all_options_together(self):
        p = _build_sysparm_params(
            25,
            50,
            query="active=true",
            display_value="all",
            exclude_reference_link=True,
            order_by="ASCname",
            fields="sys_id,name",
        )
        assert p["sysparm_limit"] == 25
        assert p["sysparm_offset"] == 50
        assert p["sysparm_display_value"] == "all"
        assert p["sysparm_query"] == "active=true"
        assert p["sysparm_exclude_reference_link"] == "true"
        assert p["sysparm_orderby"] == "ASCname"
        assert p["sysparm_fields"] == "sys_id,name"


# ---------------------------------------------------------------------------
# _join_query_parts
# ---------------------------------------------------------------------------


class TestJoinQueryParts:
    def test_empty_list_returns_empty_string(self):
        assert _join_query_parts([]) == ""

    def test_single_part(self):
        assert _join_query_parts(["state=1"]) == "state=1"

    def test_two_parts_joined_with_caret(self):
        assert _join_query_parts(["state=1", "priority=2"]) == "state=1^priority=2"

    def test_three_parts(self):
        result = _join_query_parts(["a=1", "b=2", "c=3"])
        assert result == "a=1^b=2^c=3"

    def test_empty_strings_skipped(self):
        assert _join_query_parts(["state=1", "", "priority=2"]) == "state=1^priority=2"

    def test_all_empty_strings_returns_empty(self):
        assert _join_query_parts(["", "", ""]) == ""

    def test_preserves_complex_or_conditions(self):
        part = "short_descriptionLIKEtest^ORdescriptionLIKEtest"
        assert _join_query_parts([part]) == part

    def test_combined_with_complex_part(self):
        parts = ["state=1", "nameLIKEfoo^ORdescLIKEfoo"]
        result = _join_query_parts(parts)
        assert result == "state=1^nameLIKEfoo^ORdescLIKEfoo"

    def test_does_not_mutate_input(self):
        parts = ["x=1", "y=2"]
        _ = _join_query_parts(parts)
        assert parts == ["x=1", "y=2"]


# ---------------------------------------------------------------------------
# _paginated_list_response
# ---------------------------------------------------------------------------


class TestPaginatedListResponse:
    def test_basic_structure(self):
        items = [{"id": "1"}, {"id": "2"}]
        r = _paginated_list_response(items, 10, 0, "records")
        assert r["success"] is True
        assert r["count"] == 2
        assert r["limit"] == 10
        assert r["offset"] == 0
        assert r["records"] == items

    def test_result_key_used(self):
        r = _paginated_list_response([{"a": 1}], 5, 0, "incidents")
        assert "incidents" in r
        assert r["incidents"] == [{"a": 1}]

    def test_has_more_false_when_count_less_than_limit(self):
        r = _paginated_list_response([1, 2, 3], 10, 0, "items")
        assert r["has_more"] is False
        assert r["next_offset"] is None

    def test_has_more_true_when_count_equals_limit(self):
        items = list(range(10))
        r = _paginated_list_response(items, 10, 0, "items")
        assert r["has_more"] is True
        assert r["next_offset"] == 10

    def test_next_offset_advances_by_limit(self):
        items = list(range(5))
        r = _paginated_list_response(items, 5, 20, "items")
        assert r["has_more"] is True
        assert r["next_offset"] == 25

    def test_next_offset_none_when_partial_page(self):
        items = list(range(3))
        r = _paginated_list_response(items, 5, 10, "items")
        assert r["has_more"] is False
        assert r["next_offset"] is None

    def test_empty_result_no_more_pages(self):
        r = _paginated_list_response([], 10, 0, "entries")
        assert r["has_more"] is False
        assert r["next_offset"] is None
        assert r["count"] == 0
        assert r["entries"] == []

    def test_extra_fields_merged(self):
        r = _paginated_list_response(
            [{"x": 1}], 5, 0, "items", extra={"message": "hello", "custom": 42}
        )
        assert r["message"] == "hello"
        assert r["custom"] == 42

    def test_extra_none_no_error(self):
        r = _paginated_list_response([1], 5, 0, "items", extra=None)
        assert r["success"] is True

    def test_extra_does_not_override_core_keys(self):
        # 'extra' is merged after core keys; if it overwrites count that's
        # the caller's responsibility — verify core keys come from items
        items = [1, 2]
        r = _paginated_list_response(items, 10, 0, "items")
        assert r["count"] == 2

    def test_offset_preserved_in_response(self):
        r = _paginated_list_response([1], 10, 30, "items")
        assert r["offset"] == 30

    def test_limit_preserved_in_response(self):
        r = _paginated_list_response([1], 50, 0, "items")
        assert r["limit"] == 50

    def test_page_boundary_single_item_at_limit_1(self):
        r = _paginated_list_response([{"x": 1}], 1, 0, "items")
        assert r["has_more"] is True
        assert r["next_offset"] == 1

    def test_second_page(self):
        items = list(range(10))
        r = _paginated_list_response(items, 10, 10, "items")
        assert r["offset"] == 10
        assert r["has_more"] is True
        assert r["next_offset"] == 20
