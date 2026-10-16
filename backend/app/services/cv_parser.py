import asyncio
import io
import logging
import re
import zipfile
from dataclasses import dataclass, field

import pdfplumber
from docx import Document
from docx.enum.dml import MSO_THEME_COLOR
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import RGBColor
from docx.table import Table
from docx.text.hyperlink import Hyperlink
from docx.text.paragraph import Paragraph
from fastapi import UploadFile

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
# A DOCX is a zip: a small file can expand to gigabytes of XML (a "zip bomb").
MAX_DOCX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50 MB
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".doc")
# A CV never needs more. Longer files are usually several CVs merged into one.
MAX_PDF_PAGES = 5
# Roughly 5 dense pages. Unlike the page cap it also covers DOCX, and it bounds LLM cost.
MAX_TEXT_CHARS = 20_000

# Text smaller than this (in points) can't be read on screen or on paper.
MIN_VISIBLE_FONT_SIZE = 3
# A few stray hidden characters (a white separator, a tiny bullet) aren't worth a warning.
HIDDEN_TEXT_WARNING_THRESHOLD = 10

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Digits with optional +, spaces, dots, dashes or parentheses, on a single line.
_PHONE_RE = re.compile(r"\+?\d[\d \t().-]{7,}\d")
# Runs of years such as "2015 - 2018 2019" also match the phone pattern.
_YEARS_ONLY_RE = re.compile(r"^(?:\D*(?:19|20)\d\d)+\D*$")
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
# DOCX shading fills that mean "no background".
_NO_FILL = {"auto", "FFFFFF"}


class CVParseError(ValueError):
    """Raised when a CV file can't be read or has no extractable text."""


@dataclass
class ParsedCV:
    """The visible text of a CV and any warnings about the file for the user."""

    text: str
    warnings: list[str] = field(default_factory=list)


async def parse_cv_upload(cv_file: UploadFile) -> ParsedCV:
    """Reads an uploaded CV without exceeding the size limit and parses it off the event loop."""
    # Reading one byte past the limit is enough to know it's too big without loading all of it.
    content = await cv_file.read(MAX_FILE_SIZE + 1)
    return await asyncio.to_thread(parse_cv_file, content, cv_file.filename or "")


def parse_cv_file(content: bytes, filename: str) -> ParsedCV:
    """Extracts the visible text of a PDF or DOCX CV, raising CVParseError if there is none.

    Hidden text (invisible, tiny or off the page) is left out, so instructions aimed at the
    LLM never reach it, and reported in the warnings.
    """
    if len(content) > MAX_FILE_SIZE:
        raise CVParseError("El archivo supera el tamaño máximo de 10 MB.")

    try:
        text, hidden_chars = _parse_by_extension(content, filename)
    except CVParseError:
        raise
    except Exception:
        # The parser's own message is logged, not returned: it can expose library internals.
        logger.exception("Failed to parse CV file %r", filename)
        raise CVParseError(f"No se pudo leer el archivo '{filename}'. Comprueba que no está dañado.")

    if not text.strip():
        raise CVParseError("No se pudo extraer texto del CV. Asegúrate de que el PDF no es una imagen escaneada.")
    if len(text) > MAX_TEXT_CHARS:
        raise CVParseError("El CV es demasiado largo. Sube solo un CV por archivo.")

    warnings = []
    if hidden_chars >= HIDDEN_TEXT_WARNING_THRESHOLD:
        logger.warning("CV file %r contains %d hidden characters", filename, hidden_chars)
        warnings.append(
            "El CV contiene texto oculto (invisible o de tamaño minúsculo) que se ha ignorado en el análisis. "
            "Los sistemas de selección pueden considerarlo un intento de manipulación."
        )
    if multiple_cv_warning := detect_multiple_cvs(text):
        warnings.append(multiple_cv_warning)
    return ParsedCV(text=text, warnings=warnings)


def detect_multiple_cvs(text: str) -> str | None:
    """Returns a warning if the text looks like more than one CV: several distinct emails or phones.

    Only a warning, never a rejection: a references section can legitimately list other people's contacts.
    """
    emails = {email.lower().rstrip(".") for email in _EMAIL_RE.findall(text)}
    phones = set()
    for match in _PHONE_RE.findall(text):
        if _YEARS_ONLY_RE.match(match):
            continue
        digits = re.sub(r"\D", "", match)
        if 9 <= len(digits) <= 15:
            # The last 9 digits identify the number whether or not it's written with a country code.
            phones.add(digits[-9:])

    if len(emails) > 1 or len(phones) > 1:
        return (
            "Este archivo parece contener más de un CV (hay varios emails o teléfonos distintos). "
            "Si es así, sube solo un CV por archivo."
        )
    return None


def _parse_by_extension(content: bytes, filename: str) -> tuple[str, int]:
    """Returns the visible text and how many non-space characters were hidden."""
    lower = filename.lower()

    if lower.endswith(".pdf"):
        return _parse_pdf(content)

    if lower.endswith(".docx"):
        return _parse_docx(content)

    if lower.endswith(".doc"):
        raise CVParseError("El formato .doc antiguo no está soportado. Convierte el archivo a .docx o PDF.")

    raise CVParseError(f"Formato no soportado: '{filename}'. Usa PDF o DOCX.")


# --- PDF ---


def _parse_pdf(content: bytes) -> tuple[str, int]:
    parts: list[str] = []
    hidden_chars = 0
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        if len(pdf.pages) > MAX_PDF_PAGES:
            raise CVParseError(
                f"El PDF tiene demasiadas páginas (máximo {MAX_PDF_PAGES}). Sube solo un CV por archivo."
            )
        for page in pdf.pages:
            dark_areas = _pdf_dark_areas(page)
            hidden = [char for char in page.chars if _is_hidden_pdf_char(char, page.bbox, dark_areas)]
            hidden_chars += sum(1 for char in hidden if not char["text"].isspace())

            hidden_ids = {id(char) for char in hidden}
            visible_page = page.filter(lambda obj: id(obj) not in hidden_ids)
            text = visible_page.extract_text()
            if text:
                parts.append(text)
    return "\n\n".join(parts), hidden_chars


def _pdf_dark_areas(page) -> list[dict]:
    """Images and filled shapes that white text can sit on and still be readable."""
    shapes = [s for s in page.rects + page.curves if s.get("fill") and not _is_white_pdf_color(s.get("non_stroking_color"))]
    return shapes + page.images


def _is_hidden_pdf_char(char: dict, page_bbox: tuple, dark_areas: list[dict]) -> bool:
    if char["size"] < MIN_VISIBLE_FONT_SIZE:
        return True

    x = (char["x0"] + char["x1"]) / 2
    y = (char["top"] + char["bottom"]) / 2
    left, top, right, bottom = page_bbox
    if not (left <= x <= right and top <= y <= bottom):
        return True

    if _is_white_pdf_color(char["non_stroking_color"]):
        on_dark = any(a["x0"] <= x <= a["x1"] and a["top"] <= y <= a["bottom"] for a in dark_areas)
        return not on_dark
    return False


def _is_white_pdf_color(color) -> bool:
    """True for white in grayscale (1), RGB (1, 1, 1) or CMYK (0, 0, 0, 0)."""
    if isinstance(color, (int, float)):
        color = (color,)
    if not isinstance(color, (tuple, list)):
        return False
    try:
        values = [float(v) for v in color]
    except (TypeError, ValueError):
        return False  # Pattern colors are named, not numeric.

    if len(values) in (1, 3):
        return all(v >= 0.95 for v in values)
    if len(values) == 4:
        return all(v <= 0.05 for v in values)
    return False


# --- DOCX ---


def _parse_docx(content: bytes) -> tuple[str, int]:
    _check_docx_uncompressed_size(content)
    doc = Document(io.BytesIO(content))
    page_has_background = _has_fill(doc.element.xpath("./w:background/@w:color"))
    reader = _DocxReader(page_has_background)

    # Many CV templates put the name and contact details in the header.
    for section in doc.sections:
        for part in (section.header, section.footer):
            if not part.is_linked_to_previous:
                reader.read_blocks(part, shaded=False)

    reader.read_blocks(doc, shaded=False)
    return "\n".join(reader.lines), reader.hidden_chars


def _check_docx_uncompressed_size(content: bytes) -> None:
    # zipfile stops reading an entry at its declared size, so these sizes can't be understated.
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        total = sum(info.file_size for info in archive.infolist())
    if total > MAX_DOCX_UNCOMPRESSED_SIZE:
        raise CVParseError("El archivo DOCX es demasiado grande una vez descomprimido.")


class _DocxReader:
    """Collects the visible lines of a DOCX in reading order and counts hidden characters."""

    def __init__(self, page_has_background: bool):
        self.page_has_background = page_has_background
        self.lines: list[str] = []
        self.hidden_chars = 0

    def read_blocks(self, container, shaded: bool) -> None:
        """Reads a body, header or cell, including (nested) tables. `shaded`: a fill is behind it."""
        for block in container.iter_inner_content():
            if isinstance(block, Paragraph):
                self._read_paragraph(block, shaded)
            elif isinstance(block, Table):
                self._read_table(block, shaded)

    def _read_table(self, table: Table, shaded: bool) -> None:
        table_shaded = shaded or _has_fill(table._tbl.xpath("./w:tblPr/w:shd/@w:fill"))
        if table.style is not None:
            table_shaded = table_shaded or _has_fill(table.style.element.xpath(".//w:shd/@w:fill"))

        for row in table.rows:
            seen = set()
            for cell in row.cells:
                # A merged cell is returned once per column it spans; read it only once.
                if cell._tc in seen:
                    continue
                seen.add(cell._tc)
                cell_shaded = table_shaded or _has_fill(cell._tc.xpath("./w:tcPr/w:shd/@w:fill"))
                self.read_blocks(cell, cell_shaded)

    def _read_paragraph(self, paragraph: Paragraph, shaded: bool) -> None:
        shaded = shaded or _has_fill(paragraph._p.xpath("./w:pPr/w:shd/@w:fill"))
        if paragraph.style is not None:
            shaded = shaded or _has_fill(paragraph.style.element.xpath("./w:pPr/w:shd/@w:fill"))

        runs = []
        for item in paragraph.iter_inner_content():
            runs.extend(item.runs if isinstance(item, Hyperlink) else [item])

        visible = []
        for run in runs:
            if self._is_hidden_run(run, shaded):
                self.hidden_chars += sum(1 for char in run.text if not char.isspace())
            else:
                visible.append(run.text)

        text = "".join(visible)
        if text.strip():
            self.lines.append(text)

    def _is_hidden_run(self, run, shaded: bool) -> bool:
        font = run.font
        if font.hidden:
            return True
        if font.size is not None and font.size.pt < MIN_VISIBLE_FONT_SIZE:
            return True

        is_white = font.color.rgb == _WHITE or font.color.theme_color == MSO_THEME_COLOR.BACKGROUND_1
        if not is_white:
            return False
        on_dark = (
            shaded
            or self.page_has_background
            or font.highlight_color not in (None, WD_COLOR_INDEX.WHITE)
            or _has_fill(run._r.xpath("./w:rPr/w:shd/@w:fill"))
        )
        return not on_dark


def _has_fill(fills: list[str]) -> bool:
    return any(fill.upper() not in _NO_FILL for fill in fills)
