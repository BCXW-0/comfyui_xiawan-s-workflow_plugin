"""Import structured tag libraries from text and Word documents.

The source documents used by the tag library are mostly manually formatted.
This module therefore uses Word outline levels where available and falls back
to the document's title/tag paragraph rhythm for the records below a category.
"""

from __future__ import annotations

import io
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unicodedata
import uuid
import zipfile
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{" + WORD_NS + "}"
NS = {"w": WORD_NS}
DEFAULT_COLOR = "rgba(255, 123, 2, .4)"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
UUID_NAMESPACE = uuid.UUID("5f8b1f5a-9d2d-4b3b-91ed-4ca4f1c9d245")
SKIP_HEADINGS = {"一些前言", "目录"}


class ImportFormatError(ValueError):
    """Raised when the uploaded document cannot be converted to tag SQL."""


def _clean_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("\u00a0", " ").replace("\u200b", "")
    return " ".join(value.split()).strip()


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag in {W + "tab", W + "br", W + "cr"}:
            parts.append(" ")
    return _clean_text("".join(parts))


def _paragraph_level(paragraph: ET.Element) -> int | None:
    value = paragraph.find("w:pPr/w:outlineLvl", NS)
    if value is None:
        return None
    try:
        level = int(value.get(W + "val", ""))
        return level if 0 <= level <= 3 else None
    except (TypeError, ValueError):
        return None


def _paragraph_style(paragraph: ET.Element) -> str:
    value = paragraph.find("w:pPr/w:pStyle", NS)
    return (value.get(W + "val", "") if value is not None else "").lower()


def _is_toc_paragraph(text: str, style: str) -> bool:
    if style.startswith("toc") or "\uf06c" in text:
        return True
    return False


def _is_tag_like(text: str) -> bool:
    """Recognize prompt-like lines without attempting semantic validation."""

    if not text:
        return False
    markers = (
        ",",
        "::",
        "{{",
        "}}",
        "[[",
        "]]",
        "artist:",
        "char1:",
        "char2:",
        "char3:",
        "1girl",
        "1boy",
        "2girls",
        "2boys",
    )
    if any(marker in text.lower() for marker in markers):
        return True
    ascii_count = sum(char.isascii() and char.isalpha() for char in text)
    return len(text) >= 32 and ascii_count >= 12


def _stable_uuid(kind: str, *parts: str) -> str:
    key = "|".join(_clean_text(part).casefold() for part in parts)
    return str(uuid.uuid5(UUID_NAMESPACE, f"{kind}|{key}"))


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _new_category(categories: OrderedDict, group_name: str, subgroup_name: str) -> None:
    key = (group_name, subgroup_name)
    if key not in categories:
        categories[key] = None


def _drop_empty_default_categories(categories: OrderedDict, records: list[dict]) -> None:
    tag_categories = {(record["group"], record["subgroup"]) for record in records}
    for key in list(categories):
        group_name, subgroup_name = key
        if (
            subgroup_name == "默认"
            and key not in tag_categories
            and any(
                other_group == group_name and other_subgroup != "默认"
                for other_group, other_subgroup in categories
            )
        ):
            del categories[key]


def _build_sql(categories: OrderedDict, records: list[dict]) -> tuple[list[str], dict]:
    statements: list[str] = []
    now = int(time.time() * 1000)
    group_uuids: dict[str, str] = {}
    subgroup_uuids: dict[tuple[str, str], str] = {}

    for group_name, _subgroup_name in categories:
        group_uuids.setdefault(group_name, _stable_uuid("group", group_name))

    for group_name in group_uuids:
        group_uuid = group_uuids[group_name]
        offset = len(statements)
        statements.append(
            "INSERT OR REPLACE INTO \"tag_groups\" "
            "(\"name\", \"color\", \"create_time\", \"p_uuid\") VALUES "
            f"({_sql_literal(group_name)}, {_sql_literal(DEFAULT_COLOR)}, "
            f"{now + offset}, {_sql_literal(group_uuid)});"
        )

    for group_name, subgroup_name in categories:
        group_uuid = group_uuids[group_name]
        subgroup_key = (group_name, subgroup_name)
        subgroup_uuid = subgroup_uuids.setdefault(
            subgroup_key, _stable_uuid("subgroup", group_name, subgroup_name)
        )
        offset = len(statements)
        statements.append(
            "INSERT OR REPLACE INTO \"tag_subgroups\" "
            "(\"group_id\", \"name\", \"color\", \"create_time\", \"p_uuid\", \"g_uuid\") VALUES "
            f"((SELECT \"id_index\" FROM \"tag_groups\" WHERE \"p_uuid\" = "
            f"{_sql_literal(group_uuid)} LIMIT 1), {_sql_literal(subgroup_name)}, "
            f"{_sql_literal(DEFAULT_COLOR)}, {now + offset}, {_sql_literal(group_uuid)}, "
            f"{_sql_literal(subgroup_uuid)});"
        )

    occurrences: Counter[tuple[str, str, str]] = Counter()
    for index, record in enumerate(records, start=1):
        group_name = record["group"]
        subgroup_name = record["subgroup"]
        subgroup_uuid = subgroup_uuids[(group_name, subgroup_name)]
        identity = (group_name, subgroup_name, record["text"])
        occurrence = occurrences[identity]
        occurrences[identity] += 1
        tag_uuid = _stable_uuid(
            "tag",
            group_name,
            subgroup_name,
            record["text"],
            str(occurrence),
        )
        statements.append(
            "INSERT OR REPLACE INTO \"tag_tags\" "
            "(\"subgroup_id\", \"text\", \"desc\", \"color\", \"create_time\", \"g_uuid\", \"t_uuid\") VALUES "
            f"((SELECT \"id_index\" FROM \"tag_subgroups\" WHERE \"g_uuid\" = "
            f"{_sql_literal(subgroup_uuid)} LIMIT 1), {_sql_literal(record['text'])}, "
            f"{_sql_literal(record['desc'])}, {_sql_literal(DEFAULT_COLOR)}, "
            f"{now + len(categories) * 2 + index}, "
            f"{_sql_literal(subgroup_uuid)}, {_sql_literal(tag_uuid)});"
        )

    summary = {
        "groups": len(group_uuids),
        "subgroups": len(subgroup_uuids),
        "tags": len(records),
        "statements": len(statements),
    }
    return statements, summary


def _docx_paragraphs(data: bytes) -> list[dict]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        document_xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ImportFormatError("DOCX 文件结构无法读取") from exc

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        raise ImportFormatError("DOCX 文档内容无法解析") from exc

    result = []
    for paragraph in root.findall(".//w:body/w:p", NS):
        text = _paragraph_text(paragraph)
        if not text:
            continue
        result.append(
            {
                "text": text,
                "level": _paragraph_level(paragraph),
                "style": _paragraph_style(paragraph),
            }
        )
    return result


def _records_from_docx(data: bytes) -> tuple[OrderedDict, list[dict]]:
    paragraphs = _docx_paragraphs(data)
    categories: OrderedDict = OrderedDict()
    records: list[dict] = []
    stack: dict[int, str] = {}
    current_group: str | None = None
    pending_desc = ""
    body_started = False

    for paragraph in paragraphs:
        text = paragraph["text"]
        level = paragraph["level"]
        if _is_toc_paragraph(text, paragraph["style"]):
            continue

        if level is not None:
            if text in SKIP_HEADINGS:
                continue
            if level == 0:
                current_group = text
                stack = {0: text}
                body_started = True
            elif not body_started or current_group is None:
                continue
            else:
                stack[level] = text
                for old_level in list(stack):
                    if old_level > level:
                        del stack[old_level]
            pending_desc = ""
            if current_group is not None:
                lower_levels = [stack[key] for key in sorted(stack) if key > 0]
                subgroup = " / ".join(lower_levels) if lower_levels else "默认"
                _new_category(categories, current_group, subgroup)
            continue

        if not body_started or current_group is None:
            continue
        lower_levels = [stack[key] for key in sorted(stack) if key > 0]
        subgroup = " / ".join(lower_levels) if lower_levels else "默认"
        _new_category(categories, current_group, subgroup)

        if _is_tag_like(text):
            records.append(
                {
                    "group": current_group,
                    "subgroup": subgroup,
                    "text": text,
                    "desc": pending_desc,
                }
            )
            pending_desc = ""
        else:
            pending_desc = _clean_text(
                " ".join(part for part in (pending_desc, text) if part)
            )

    if not categories:
        raise ImportFormatError("DOCX 中未找到可识别的正文分类")
    if not records:
        raise ImportFormatError("DOCX 中未找到可导入的 Tag 内容")

    _drop_empty_default_categories(categories, records)
    return categories, records


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFormatError("TXT 文件编码无法识别，请使用 UTF-8、UTF-16 或 GB18030")


def _records_from_txt(data: bytes, filename: str) -> tuple[OrderedDict, list[dict]]:
    text = _decode_text(data)
    categories: OrderedDict = OrderedDict()
    records: list[dict] = []
    group_name = _clean_text(Path(filename).stem) or "TXT 导入"
    subgroup_name = "默认"

    def ensure_category() -> None:
        _new_category(categories, group_name, subgroup_name)

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        if line.startswith("### "):
            subgroup_name = _clean_text(line[4:]) or "默认"
            ensure_category()
            continue
        if line.startswith("## "):
            subgroup_name = _clean_text(line[3:]) or "默认"
            ensure_category()
            continue
        if line.startswith("# "):
            group_name = _clean_text(line[2:]) or group_name
            subgroup_name = "默认"
            ensure_category()
            continue

        ensure_category()
        if "\t" in line:
            tag_text, desc = line.split("\t", 1)
        elif "||" in line:
            tag_text, desc = line.split("||", 1)
        elif line.count(",") == 1:
            tag_text, desc = line.split(",", 1)
        else:
            tag_text, desc = line, ""
        tag_text = _clean_text(tag_text)
        if tag_text:
            records.append(
                {
                    "group": group_name,
                    "subgroup": subgroup_name,
                    "text": tag_text,
                    "desc": _clean_text(desc),
                }
            )

    if not records:
        raise ImportFormatError("TXT 中未找到可导入的 Tag 内容")
    _drop_empty_default_categories(categories, records)
    return categories, records


def _find_soffice() -> str | None:
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    return next((candidate for candidate in candidates if candidate and os.path.isfile(candidate)), None)


def _convert_doc_to_docx(data: bytes, filename: str) -> bytes:
    soffice = _find_soffice()
    if not soffice:
        raise ImportFormatError("解析 DOC 需要安装 LibreOffice，或先另存为 DOCX")

    with tempfile.TemporaryDirectory(prefix="tag_import_") as temp_dir:
        source_path = Path(temp_dir) / (Path(filename).stem + ".doc")
        source_path.write_bytes(data)
        command = [
            soffice,
            "--headless",
            "--convert-to",
            "docx",
            "--outdir",
            temp_dir,
            str(source_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ImportFormatError("DOC 转换失败，请确认文件可以被 Word 或 LibreOffice 打开") from exc
        output_path = Path(temp_dir) / (source_path.stem + ".docx")
        if not output_path.is_file():
            raise ImportFormatError("DOC 转换后没有生成可读取的 DOCX")
        return output_path.read_bytes()


def parse_source(filename: str, data: bytes) -> tuple[list[str], dict]:
    if len(data) > MAX_SOURCE_BYTES:
        raise ImportFormatError("文件超过 64 MB，无法导入")
    extension = Path(filename).suffix.lower()
    if extension == ".txt":
        categories, records = _records_from_txt(data, filename)
    elif extension == ".docx":
        categories, records = _records_from_docx(data)
    elif extension == ".doc":
        if data.startswith(b"PK"):
            categories, records = _records_from_docx(data)
        elif b"\x00" not in data[:4096]:
            categories, records = _records_from_txt(data, filename)
        else:
            categories, records = _records_from_docx(_convert_doc_to_docx(data, filename))
    else:
        raise ImportFormatError("仅支持 TXT、DOC 或 DOCX 文件")

    statements, summary = _build_sql(categories, records)
    _validate_sql(statements)
    summary["source_format"] = extension[1:].upper()
    return statements, summary


def _validation_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE tag_groups (
            id_index INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, color TEXT, create_time INTEGER, p_uuid TEXT
        );
        CREATE TABLE tag_subgroups (
            id_index INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER, name TEXT, color TEXT, create_time INTEGER,
            p_uuid TEXT, g_uuid TEXT
        );
        CREATE TABLE tag_tags (
            id_index INTEGER PRIMARY KEY AUTOINCREMENT,
            subgroup_id INTEGER, text TEXT, desc TEXT, color TEXT,
            create_time INTEGER, t_uuid TEXT, g_uuid TEXT
        );
        CREATE UNIQUE INDEX tag_groups_uuid ON tag_groups(p_uuid);
        CREATE UNIQUE INDEX tag_subgroups_uuid ON tag_subgroups(g_uuid);
        CREATE UNIQUE INDEX tag_tags_uuid ON tag_tags(t_uuid);
        """
    )


def _validate_sql(statements: Iterable[str]) -> None:
    connection = sqlite3.connect(":memory:")
    try:
        _validation_schema(connection)
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.rollback()
    except sqlite3.Error as exc:
        raise ImportFormatError(f"生成的 SQL 无法执行：{exc}") from exc
    finally:
        connection.close()


def _ensure_tags_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS tag_groups (
            id_index INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, color TEXT, create_time INTEGER, p_uuid TEXT
        );
        CREATE TABLE IF NOT EXISTS tag_subgroups (
            id_index INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER, name TEXT, color TEXT, create_time INTEGER,
            p_uuid TEXT, g_uuid TEXT
        );
        CREATE TABLE IF NOT EXISTS tag_tags (
            id_index INTEGER PRIMARY KEY AUTOINCREMENT,
            subgroup_id INTEGER, text TEXT, desc TEXT, color TEXT,
            create_time INTEGER, t_uuid TEXT, g_uuid TEXT
        );
        """
    )
    required = {
        "tag_groups": {"p_uuid": "TEXT(128)"},
        "tag_subgroups": {"p_uuid": "TEXT(128)", "g_uuid": "TEXT(128)"},
        "tag_tags": {"t_uuid": "TEXT(128)", "g_uuid": "TEXT(128)"},
    }
    for table, columns in required.items():
        existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    for index_name, table, column in (
        ("tag_groups_uuid", "tag_groups", "p_uuid"),
        ("tag_subgroups_uuid", "tag_subgroups", "g_uuid"),
        ("tag_tags_uuid", "tag_tags", "t_uuid"),
    ):
        try:
            connection.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
                f"ON {table}({column})"
            )
        except sqlite3.IntegrityError:
            # Legacy databases may already contain duplicate or empty UUIDs.
            # The host migration will repair those rows on its normal startup.
            pass


def import_to_tags_database(filename: str, data: bytes) -> dict:
    statements, summary = parse_source(filename, data)

    from ..dao.dao import get_db_path

    db_path = get_db_path("tags")
    connection = sqlite3.connect(db_path)
    try:
        _ensure_tags_schema(connection)
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    try:
        from ..prompt_api.tags_manager import _invalidate_cache

        _invalidate_cache()
    except Exception:
        pass

    output_dir = Path(db_path).parent / "intelligent_tag_imports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"tag_library_{time.time_ns()}.sql"
    output_path.write_text("\n".join(statements) + "\n", encoding="utf-8")
    summary["sql_file"] = str(output_path)
    summary["source_name"] = Path(filename).name
    return summary
