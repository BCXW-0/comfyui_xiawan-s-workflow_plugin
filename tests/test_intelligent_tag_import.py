from __future__ import annotations

import io
import re
import sqlite3
import sys
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vendor.weilin_tools.app.server.panel_server.intelligent_tag_import import (
    _records_from_docx,
    _records_from_txt,
    _validation_schema,
    parse_source,
)


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx_bytes(paragraphs):
    body = []
    for text, level in paragraphs:
        ppr = f'<w:pPr><w:outlineLvl w:val="{level}" /></w:pPr>' if level is not None else ""
        body.append(f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>")
    document = (
        f'<w:document xmlns:w="{WORD_NS}"><w:body>{"".join(body)}'
        "</w:body></w:document>"
    ).encode("utf-8")
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("word/document.xml", document)
    return result.getvalue()


def test_txt_import_supports_existing_and_prompt_lines():
    categories, records = _records_from_txt(
        b"# Main\n## Group\ntag,description\n1girl,solo,highres\n",
        "library.txt",
    )

    assert list(categories) == [("Main", "Group")]
    assert records[0]["text"] == "tag"
    assert records[0]["desc"] == "description"
    assert records[1]["text"] == "1girl,solo,highres"
    assert records[1]["desc"] == ""


def test_docx_outline_levels_flatten_into_existing_two_level_schema():
    data = _docx_bytes(
        [
            ("Main", 0),
            ("Section", 1),
            ("Entry", None),
            ("tag one,tag two", None),
            ("Deep", 2),
            ("Deep entry", None),
            ("tag three,tag four", None),
            ("Odd entry", 9),
            ("tag five,tag six", None),
        ]
    )

    categories, records = _records_from_docx(data)

    assert list(categories) == [("Main", "Section"), ("Main", "Section / Deep")]
    assert [record["desc"] for record in records] == ["Entry", "Deep entry", "Odd entry"]


def test_docx_keeps_consecutive_non_tag_description_lines():
    data = _docx_bytes(
        [
            ("Main", 0),
            ("Section", 1),
            ("First description", None),
            ("Second description", None),
            ("tag one,tag two", None),
        ]
    )

    _categories, records = _records_from_docx(data)

    assert records[0]["desc"] == "First description Second description"


def test_sql_is_executable_and_uuid_values_are_stable():
    data = _docx_bytes(
        [("Main", 0), ("Section", 1), ("Entry", None), ("tag one,tag two", None)]
    )
    statements_a, summary_a = parse_source("library.docx", data)
    statements_b, summary_b = parse_source("library.docx", data)
    changed_description = _docx_bytes(
        [
            ("Main", 0),
            ("Section", 1),
            ("Updated description", None),
            ("tag one,tag two", None),
        ]
    )
    statements_c, _summary_c = parse_source("library.docx", changed_description)

    assert summary_a == summary_b
    assert summary_a["groups"] == 1
    assert summary_a["subgroups"] == 1
    assert summary_a["tags"] == 1
    uuid_values_a = re.findall(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "\n".join(statements_a))
    uuid_values_b = re.findall(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "\n".join(statements_b))
    uuid_values_c = re.findall(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "\n".join(statements_c))
    assert uuid_values_a == uuid_values_b
    assert uuid_values_a == uuid_values_c
    assert sum('INSERT OR REPLACE INTO "tag_groups"' in item for item in statements_a) == 1

    connection = sqlite3.connect(":memory:")
    try:
        _validation_schema(connection)
        for statement in statements_a:
            connection.execute(statement)
        assert connection.execute("SELECT group_id FROM tag_subgroups").fetchone() == (1,)
        assert connection.execute("SELECT subgroup_id FROM tag_tags").fetchone() == (1,)
    finally:
        connection.close()
