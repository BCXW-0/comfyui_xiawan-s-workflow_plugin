import asyncio
import sys
import types
import uuid

if "uuid_extensions" not in sys.modules:
    uuid_extensions = types.ModuleType("uuid_extensions")
    uuid_extensions.uuid7 = uuid.uuid4
    sys.modules["uuid_extensions"] = uuid_extensions

from vendor.weilin_tools.app.server.prompt_api import tags_manager


def test_tag_page_is_bounded_and_reports_more_rows(monkeypatch):
    captured = {}

    async def fake_fetch_all(db_type, query, params=None):
        captured["db_type"] = db_type
        captured["query"] = query
        captured["params"] = params
        return [
            (index, f"tag-{index}", "", "", index, "group", f"uuid-{index}", "", None)
            for index in range(501)
        ]

    monkeypatch.setattr(tags_manager, "fetch_all", fake_fetch_all)

    result = asyncio.run(tags_manager.get_tag_tags_page("group", page=2, page_size=999))

    assert len(result["data"]) == 500
    assert result["page"] == 2
    assert result["page_size"] == 500
    assert result["has_more"] is True
    assert captured["db_type"] == "tags"
    assert captured["params"] == ("group", 501, 500)
    assert "LIMIT ? OFFSET ?" in captured["query"]


def test_group_tree_does_not_read_tag_rows_by_default(monkeypatch):
    captured = {}

    async def fake_fetch_all(db_type, query, params=None):
        captured["query"] = query
        return [(1, "Category", "", 1, "category", 2, "Group", "", 2, "group", "category")]

    monkeypatch.setattr(tags_manager, "fetch_all", fake_fetch_all)

    result = asyncio.run(tags_manager.get_group_tags())

    assert result[0]["name"] == "Category"
    assert result[0]["groups"][0]["name"] == "Group"
    assert result[0]["groups"][0]["tags"] == []
    assert "tag_tags" not in captured["query"]
