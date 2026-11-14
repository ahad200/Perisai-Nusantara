"""Penulis PDF minimal tanpa dependensi (PRD FR-601: laporan diekspor ke PDF).

Laporan F1 adalah template deterministik, jadi tak perlu mesin PDF berat
(reportlab/weasyprint) yang menambah dependensi/rebuild image dan rantai pasok.
Modul ini membuat PDF 1.4 valid memakai font standar **Helvetica/Helvetica-Bold**
(14 font bawaan PDF, tanpa embedding, tanpa jaringan). Mendukung judul, heading,
paragraf (word-wrap), baris kunci–nilai, tabel sederhana, dan penggantian halaman
otomatis.

Dokumen dibangun dari daftar "flowable" via kelas `PdfReport`, lalu `render()`
mengembalikan `bytes` PDF.
"""
from __future__ import annotations

PAGE_W, PAGE_H = 595.0, 842.0  # A4 points
MARGIN = 50.0
# Lebar karakter rata-rata Helvetica (~0.5em); konservatif agar teks tak meluber.
_AVG_W = 0.52


# Karakter di luar WinAnsiEncoding (cp1252) → padanan ASCII agar tak jadi "?".
_FALLBACK = str.maketrans({
    "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≠": "!=", "−": "-", "✓": "v",
})


def _esc(text: str) -> str:
    """Escape untuk literal string PDF + paksa ke cp1252 (WinAnsiEncoding)."""
    out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return out.translate(_FALLBACK).encode("cp1252", "replace").decode("cp1252")


def _max_chars(width: float, size: float) -> int:
    return max(1, int(width / (_AVG_W * size)))


def _wrap(text: str, width: float, size: float) -> list[str]:
    limit = _max_chars(width, size)
    words = str(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = w if not cur else f"{cur} {w}"
        if len(cand) <= limit:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            # kata tunggal lebih panjang dari baris → potong keras
            while len(w) > limit:
                lines.append(w[:limit])
                w = w[limit:]
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _truncate(text: str, width: float, size: float) -> str:
    limit = _max_chars(width, size)
    text = str(text)
    return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"


class PdfReport:
    def __init__(self) -> None:
        # Setiap elemen: ("op", ...). Tata letak dilakukan saat render.
        self._items: list[tuple] = []

    # -- API penyusunan ---------------------------------------------------- #
    def title(self, text: str) -> None:
        self._items.append(("title", text))

    def heading(self, text: str) -> None:
        self._items.append(("heading", text))

    def paragraph(self, text: str) -> None:
        self._items.append(("para", text))

    def kv(self, key: str, value: str) -> None:
        self._items.append(("kv", key, value))

    def spacer(self, h: float = 8.0) -> None:
        self._items.append(("spacer", h))

    def rule(self) -> None:
        self._items.append(("rule",))

    def table(self, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
        self._items.append(("table", headers, rows, widths))

    # -- Render ------------------------------------------------------------ #
    def render(self) -> bytes:
        pages: list[list[str]] = []  # tiap halaman = daftar potongan content stream
        avail_w = PAGE_W - 2 * MARGIN
        y = PAGE_H - MARGIN
        cur: list[str] = []

        def new_page() -> None:
            nonlocal cur, y
            if cur:
                pages.append(cur)
            cur = []
            y = PAGE_H - MARGIN

        def ensure(space: float) -> None:
            nonlocal y
            if y - space < MARGIN:
                new_page()

        def text(x: float, yy: float, s: str, size: float, bold: bool) -> None:
            font = "F2" if bold else "F1"
            cur.append(f"BT /{font} {size:.1f} Tf 1 0 0 1 {x:.1f} {yy:.1f} Tm ({_esc(s)}) Tj ET")

        def hline(yy: float) -> None:
            cur.append(f"0.75 w 0.80 0.80 0.80 RG {MARGIN:.1f} {yy:.1f} m {PAGE_W - MARGIN:.1f} {yy:.1f} l S")

        for item in self._items:
            kind = item[0]
            if kind == "title":
                ensure(30)
                for ln in _wrap(item[1], avail_w, 18):
                    ensure(24)
                    y -= 22
                    text(MARGIN, y, ln, 18, True)
                y -= 6
                hline(y)
                y -= 6
            elif kind == "heading":
                ensure(26)
                y -= 20
                text(MARGIN, y, item[1], 13, True)
                y -= 4
            elif kind == "para":
                for ln in _wrap(item[1], avail_w, 10):
                    ensure(15)
                    y -= 14
                    text(MARGIN, y, ln, 10, False)
            elif kind == "kv":
                key, value = item[1], item[2]
                key_w = avail_w * 0.38
                val_w = avail_w - key_w
                vlines = _wrap(value, val_w, 10)
                ensure(15)
                y -= 14
                text(MARGIN, y, _truncate(key, key_w, 10), 10, True)
                text(MARGIN + key_w, y, vlines[0], 10, False)
                for extra in vlines[1:]:
                    ensure(14)
                    y -= 13
                    text(MARGIN + key_w, y, extra, 10, False)
            elif kind == "spacer":
                y -= float(item[1])
            elif kind == "rule":
                ensure(10)
                y -= 6
                hline(y)
            elif kind == "table":
                headers, rows, widths = item[1], item[2], item[3]
                ncol = len(headers)
                if widths is None:
                    widths = [avail_w / ncol] * ncol
                else:
                    total = sum(widths)
                    widths = [avail_w * w / total for w in widths]
                xs = [MARGIN]
                for w in widths[:-1]:
                    xs.append(xs[-1] + w)

                def draw_header() -> None:
                    nonlocal y
                    ensure(18)
                    y -= 15
                    for i, h in enumerate(headers):
                        text(xs[i], y, _truncate(h, widths[i] - 4, 9.5), 9.5, True)
                    y -= 3
                    hline(y)

                draw_header()
                for row in rows:
                    if y - 14 < MARGIN:
                        new_page()
                        draw_header()
                    y -= 13
                    for i in range(ncol):
                        cell = row[i] if i < len(row) else ""
                        text(xs[i], y, _truncate(cell, widths[i] - 4, 9.5), 9.5, False)
                y -= 2

        new_page()
        if not pages:
            pages = [[]]
        return _assemble(pages)


def _assemble(pages: list[list[str]]) -> bytes:
    """Rakit objek PDF + xref + trailer."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)  # nomor objek 1-indexed

    # Font bawaan (tak perlu embedding).
    font1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    pages_obj_num = len(objects) + 1  # objek /Pages berikutnya
    # Sisakan slot: Pages, lalu untuk tiap halaman: Page + Contents.
    # Hitung nomor objek halaman dulu.
    add(b"PLACEHOLDER_PAGES")  # diisi belakangan
    page_obj_nums: list[int] = []
    for page in pages:
        stream = ("\n".join(page)).encode("cp1252", "replace")
        content_num = add(
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        )
        page_num = add(
            (
                "<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.0f %.0f] "
                "/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> "
                "/Contents %d 0 R >>"
                % (pages_obj_num, PAGE_W, PAGE_H, font1, font2, content_num)
            ).encode("latin-1")
        )
        page_obj_nums.append(page_num)

    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
    objects[pages_obj_num - 1] = (
        "<< /Type /Pages /Count %d /Kids [%s] >>" % (len(page_obj_nums), kids)
    ).encode("latin-1")

    catalog_num = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj_num)

    # Serialisasi.
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"

    xref_pos = len(out)
    n = len(objects) + 1
    out += b"xref\n0 %d\n" % n
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (
        b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (n, catalog_num, xref_pos)
    )
    return bytes(out)
