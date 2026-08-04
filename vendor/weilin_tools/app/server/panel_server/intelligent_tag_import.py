"""Import structured tag libraries from text and Word-compatible documents.

The source documents used by the tag library are mostly manually formatted.
This module therefore uses Word outline levels where available and falls back
to the document's title/tag paragraph rhythm for the records below a category.
"""

from __future__ import annotations

import io
import sqlite3
import struct
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


_CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_CFB_FREESECT = 0xFFFFFFFF
_CFB_ENDOFCHAIN = 0xFFFFFFFE


class _CompoundFileReader:
    """Read streams from legacy binary Word-compatible compound documents."""

    def __init__(self, data: bytes):
        if len(data) < 512 or data[:8] != _CFB_SIGNATURE:
            raise ImportFormatError("DOC 文件不是有效的 OLE 文档")
        self.data = data
        self.sector_size = 1 << self._u16(30)
        self.mini_sector_size = 1 << self._u16(32)
        if self.sector_size not in (512, 4096) or self.mini_sector_size != 64:
            raise ImportFormatError("DOC 文件使用了不支持的 OLE 扇区格式")

        self.mini_stream_cutoff = self._u32(56)
        self.fat = self._load_fat()
        directory = self._read_regular(self._i32(48), None)
        self.entries = self._parse_directory(directory)
        self.root = next(
            (entry for entry in self.entries if entry["type"] == 5), None
        )
        if self.root is None:
            raise ImportFormatError("DOC 文件缺少 OLE 根目录")
        self.mini_fat = self._load_mini_fat()

    def _u16(self, offset: int) -> int:
        return struct.unpack_from("<H", self.data, offset)[0]

    def _u32(self, offset: int) -> int:
        return struct.unpack_from("<I", self.data, offset)[0]

    def _i32(self, offset: int) -> int:
        return struct.unpack_from("<i", self.data, offset)[0]

    def _sector(self, sector_id: int) -> bytes:
        if sector_id < 0:
            raise ImportFormatError("DOC 文件的 OLE 扇区链无效")
        start = (sector_id + 1) * self.sector_size
        end = start + self.sector_size
        if end > len(self.data):
            raise ImportFormatError("DOC 文件的 OLE 扇区超出文件范围")
        return self.data[start:end]

    def _chain(self, start: int, table: list[int]) -> list[int]:
        if start in (-1, _CFB_ENDOFCHAIN, _CFB_FREESECT):
            return []
        result = []
        current = start
        seen = set()
        while current not in (_CFB_ENDOFCHAIN, _CFB_FREESECT):
            if current < 0 or current in seen or current >= len(table):
                raise ImportFormatError("DOC 文件的 OLE 流链无效")
            seen.add(current)
            result.append(current)
            current = table[current]
        return result

    def _load_fat(self) -> list[int]:
        difat = [
            self._u32(76 + index * 4)
            for index in range(109)
            if self._u32(76 + index * 4) != _CFB_FREESECT
        ]
        current = self._i32(68)
        for _ in range(self._u32(72)):
            sector = self._sector(current)
            values = struct.unpack("<" + "I" * (self.sector_size // 4), sector)
            difat.extend(value for value in values[:-1] if value != _CFB_FREESECT)
            current = values[-1]

        fat_ids = difat[: self._u32(44)]
        if len(fat_ids) != self._u32(44):
            raise ImportFormatError("DOC 文件缺少完整的 OLE FAT")
        fat = []
        for sector_id in fat_ids:
            sector = self._sector(sector_id)
            fat.extend(struct.unpack("<" + "I" * (self.sector_size // 4), sector))
        return fat

    def _read_regular(self, start: int, size: int | None) -> bytes:
        chunks = [self._sector(sector_id) for sector_id in self._chain(start, self.fat)]
        result = b"".join(chunks)
        return result if size is None else result[:size]

    @staticmethod
    def _parse_directory(data: bytes) -> list[dict]:
        entries = []
        for offset in range(0, len(data) - 127, 128):
            name_length = struct.unpack_from("<H", data, offset + 64)[0]
            entry_type = data[offset + 66]
            if not name_length or entry_type == 0:
                continue
            raw_name = data[offset : offset + max(0, name_length - 2)]
            name = raw_name.decode("utf-16le", "replace")
            entries.append(
                {
                    "name": name,
                    "type": entry_type,
                    "start": struct.unpack_from("<i", data, offset + 116)[0],
                    "size": struct.unpack_from("<Q", data, offset + 120)[0],
                }
            )
        return entries

    def _load_mini_fat(self) -> list[int]:
        start = self._i32(60)
        count = self._u32(64)
        if count == 0 or start in (-1, _CFB_ENDOFCHAIN):
            return []
        raw = self._read_regular(start, count * self.sector_size)
        return list(struct.unpack("<" + "I" * (len(raw) // 4), raw))

    def _read_mini(self, entry: dict) -> bytes:
        root_stream = self._read_regular(self.root["start"], self.root["size"])
        chunks = []
        for sector_id in self._chain(entry["start"], self.mini_fat):
            start = sector_id * self.mini_sector_size
            chunks.append(root_stream[start : start + self.mini_sector_size])
        return b"".join(chunks)[: entry["size"]]

    def stream(self, name: str) -> bytes:
        entry = next(
            (
                item
                for item in self.entries
                if item["type"] == 2 and item["name"].casefold() == name.casefold()
            ),
            None,
        )
        if entry is None:
            raise ImportFormatError(f"DOC 文件缺少 {name} 流")
        if entry["size"] < self.mini_stream_cutoff:
            return self._read_mini(entry)
        return self._read_regular(entry["start"], entry["size"])


def _legacy_piece_table(word: bytes, table: bytes) -> list[str]:
    csw = struct.unpack_from("<H", word, 32)[0]
    position = 34 + csw * 2
    cslw = struct.unpack_from("<H", word, position)[0]
    position += 2 + cslw * 4
    cb_rg_fc_lcb = struct.unpack_from("<H", word, position)[0]
    position += 2

    # fcClx is normally pair 33; scanning also covers compatible WPS files.
    candidate_indices = [33] + [index for index in range(cb_rg_fc_lcb) if index != 33]
    for index in candidate_indices:
        if position + (index + 1) * 8 > len(word):
            continue
        fc, lcb = struct.unpack_from("<II", word, position + index * 8)
        if not lcb or fc + lcb > len(table):
            continue
        clx = table[fc : fc + lcb]
        clx_position = 0
        while clx_position < len(clx) and clx[clx_position] == 1:
            if clx_position + 5 > len(clx):
                break
            size = struct.unpack_from("<I", clx, clx_position + 1)[0]
            clx_position += 5 + size
        if clx_position + 5 > len(clx) or clx[clx_position] != 2:
            continue
        piece_table_size = struct.unpack_from("<I", clx, clx_position + 1)[0]
        piece_table = clx[clx_position + 5 : clx_position + 5 + piece_table_size]
        if len(piece_table) != piece_table_size or piece_table_size < 16:
            continue
        if (piece_table_size - 4) % 12:
            continue
        piece_count = (piece_table_size - 4) // 12
        cps = [
            struct.unpack_from("<I", piece_table, offset * 4)[0]
            for offset in range(piece_count + 1)
        ]
        if any(end < start for start, end in zip(cps, cps[1:])):
            continue

        pieces = []
        pcd_start = 4 * (piece_count + 1)
        for piece_index, (cp_start, cp_end) in enumerate(zip(cps, cps[1:])):
            pcd_offset = pcd_start + piece_index * 8
            fc_raw = struct.unpack_from("<I", piece_table, pcd_offset + 2)[0]
            compressed = bool(fc_raw & 0x40000000)
            fc_value = fc_raw & 0x3FFFFFFF
            char_count = cp_end - cp_start
            if compressed:
                fc_value >>= 1
                raw = word[fc_value : fc_value + char_count]
                text = raw.decode("cp1252", "replace")
            else:
                raw = word[fc_value : fc_value + char_count * 2]
                text = raw.decode("utf-16le", "replace")
            if len(raw) != (char_count if compressed else char_count * 2):
                break
            pieces.append(text)
        else:
            return pieces
    raise ImportFormatError("DOC 文件的 Word 文本结构无法解析")


def _extract_doc_text(data: bytes) -> str:
    compound = _CompoundFileReader(data)
    word = compound.stream("WordDocument")
    if len(word) < 34:
        raise ImportFormatError("DOC 文件的 Word 文本结构不完整")
    flags = struct.unpack_from("<H", word, 10)[0]
    if flags & 0x0100:
        raise ImportFormatError("DOC 文件已加密，无法进行智能分析")
    table_name = "1Table" if flags & 0x0200 else "0Table"
    table = compound.stream(table_name)
    try:
        text = "".join(_legacy_piece_table(word, table))
    except (IndexError, struct.error, UnicodeError) as exc:
        raise ImportFormatError("DOC 文件的 Word 文本结构无法解析") from exc
    return (
        text.replace("\x07", "\r")
        .replace("\x0c", "\r")
        .replace("\x0b", " ")
        .replace("\x08", "")
    )


def _legacy_doc_tag_like(text: str) -> bool:
    if not text:
        return False
    if any(marker in text.lower() for marker in (",", "::", "{{", "}}", "[[", "]]", "artist:", "1girl", "1boy")):
        return True
    ascii_count = sum(char.isascii() and char.isalpha() for char in text)
    has_cjk = any("\u3400" <= char <= "\u9fff" for char in text)
    return len(text) >= 32 and ascii_count >= 12 and not has_cjk


def _records_from_doc(data: bytes, filename: str) -> tuple[OrderedDict, list[dict]]:
    text = _extract_doc_text(data)
    group_name = _clean_text(Path(filename).stem) or "DOC 导入"
    subgroup_name = "默认"
    categories: OrderedDict = OrderedDict()
    records: list[dict] = []
    pending_desc = ""

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        _new_category(categories, group_name, subgroup_name)
        if _legacy_doc_tag_like(line):
            records.append(
                {
                    "group": group_name,
                    "subgroup": subgroup_name,
                    "text": line,
                    "desc": pending_desc,
                }
            )
            pending_desc = ""
        else:
            pending_desc = _clean_text(
                " ".join(part for part in (pending_desc, line) if part)
            )

    if not records:
        raise ImportFormatError("DOC 中未找到可导入的 Tag 内容")
    _drop_empty_default_categories(categories, records)
    return categories, records


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
            categories, records = _records_from_doc(data, filename)
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
