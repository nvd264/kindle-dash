"""Minimal EPUB 3 writer shared by the Kindle book builders."""
import zipfile
import xml.etree.ElementTree as ET
from html import escape

MEDIA = {"xhtml": "application/xhtml+xml", "css": "text/css", "jpg": "image/jpeg", "png": "image/png"}


def xhtml(title, body):
    doc = (f'<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" '
           f'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>{escape(title)}</title>'
           f'<link rel="stylesheet" href="style.css"/></head><body>{body}</body></html>').encode()
    ET.fromstring(doc)  # self-check: KOReader can choke on malformed XHTML, so fail the build instead
    return doc


def write_epub(out, uid, title, files, spine, nav):
    """files: {name: bytes} incl. style.css; spine: chapter names in order; nav: <ol> TOC markup."""
    files = {**files, "nav.xhtml": xhtml("Contents", f'<nav epub:type="toc"><h1>{escape(title)}</h1>{nav}</nav>')}
    ids = {name: f"i{n}" for n, name in enumerate(files)}
    manifest = "".join(
        f'<item id="{ids[name]}" href="{name}" media-type="{MEDIA[name.rsplit(".", 1)[1]]}"'
        + (' properties="nav"' if name == "nav.xhtml" else "") + "/>" for name in files)
    itemrefs = "".join(f'<itemref idref="{ids[name]}"/>' for name in spine)
    opf = ('<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">{uid}</dc:identifier>'
           f'<dc:title>{escape(title)}</dc:title><dc:creator>nvd264</dc:creator><dc:language>en</dc:language>'
           '<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata>'
           f'<manifest>{manifest}</manifest><spine>{itemrefs}</spine></package>')
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)  # must be first, uncompressed
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", opf)
        for name, blob in files.items():
            z.writestr(f"OEBPS/{name}", blob)
    print(f"{out}: {len(spine)} chapters, {out.stat().st_size // 1024} KB")
