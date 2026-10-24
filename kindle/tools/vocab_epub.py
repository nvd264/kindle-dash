#!/usr/bin/env python3
"""Turn the interview repo's vocab.js into a flashcard EPUB for KOReader.

Usage: vocab_epub.py <path/to/interview> [out.epub]
Each word becomes two pages: front (picture, word, IPA) and back (meaning, examples).
"""
import io
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

EMOJI_FONT = "/usr/share/fonts/noto/NotoColorEmoji.ttf"
CARDS_PER_FILE = 50  # big XHTML chapters make KOReader slow to paginate on the PW4

CSS = """
body { font-family: serif; margin: 0; }
.card { page-break-before: always; text-align: center; }
.front { padding-top: 12%; }
.pic { max-width: 90%; }
.emoji { height: 4em; }
.word { font-size: 2.6em; font-weight: bold; margin: 0.5em 0 0.2em; }
.meta { font-size: 1.1em; }
.lvl { border: 1px solid #000; padding: 0 0.3em; font-size: 0.9em; }
.deck { margin-top: 3em; font-size: 0.8em; color: #666; }
.back { text-align: left; padding-top: 6%; }
.head { font-size: 1.3em; font-weight: bold; }
.vi { font-size: 1.7em; font-weight: bold; margin: 0.6em 0 1em; }
.ex { font-style: italic; margin: 0.4em 0; }
.exvi { color: #444; margin: 0.2em 0 1em; }
.col { margin-top: 1em; }
.credit { margin-top: 2.5em; font-size: 0.7em; color: #666; }
"""


def xhtml(title, body):
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" '
            f'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>{escape(title)}</title>'
            f'<link rel="stylesheet" href="style.css"/></head><body>{body}</body></html>')


def gray_jpeg(src):
    img = Image.open(src)
    img.seek(0)  # first frame of animated GIFs
    img = img.convert("RGBA")
    flat = Image.new("RGBA", img.size, "white")
    flat.alpha_composite(img)
    flat = flat.convert("L")
    flat.thumbnail((800, 800))
    buf = io.BytesIO()
    flat.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def emoji_png(text, font):
    w = int(font.getlength(text)) + 8
    img = Image.new("RGBA", (max(w, 8), 128), (255, 255, 255, 0))
    ImageDraw.Draw(img).text((4, 0), text, font=font, embedded_color=True)
    flat = Image.new("RGBA", img.size, "white")
    flat.alpha_composite(img)
    flat = flat.convert("L").crop(flat.convert("L").point(lambda v: v < 250 and 255).getbbox() or (0, 0, 8, 8))
    buf = io.BytesIO()
    flat.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def card(w, deck, n, total, pic):
    word, pos, ipa, vi, ex, ex_vi, lvl, col, _, _, img, src, lic = w
    visual = f'<img class="pic" src="{pic}" alt=""/>' if img else f'<img class="emoji" src="{pic}" alt=""/>'
    front = (f'<div class="card front"><p>{visual}</p><p class="word">{escape(word)}</p>'
             f'<p class="meta">{escape(pos)} · {escape(ipa)} · <span class="lvl">{escape(lvl)}</span></p>'
             f'<p class="deck">{escape(deck)} · {n}/{total}</p></div>')
    back = (f'<div class="card back"><p class="head">{escape(word)} <span class="meta">{escape(ipa)}</span></p>'
            f'<p class="vi">{escape(vi)}</p><p class="ex">{escape(ex)}</p><p class="exvi">{escape(ex_vi)}</p>'
            + (f'<p class="col"><b>Collocations:</b> {escape(col)}</p>' if col else "")
            + (f'<p class="credit">Image: {escape(src)} — {escape(lic)}, Wikimedia Commons</p>' if img else "")
            + "</div>")
    return front + back


def build(repo, out):
    js = (repo / "assets/data/vocab.js").read_text(encoding="utf-8")
    data = json.loads(js[js.index("{"): js.rindex("}") + 1])
    decks, words = data["decks"], data["words"]
    emoji_font = ImageFont.truetype(EMOJI_FONT, 109)  # the only size this bitmap font has

    files, manifest, spine, nav = {}, [], [], []
    for d, deck in enumerate(decks):
        deck_words = [w for w in words if w[8] == d]
        assert len(deck_words) == deck["count"], (deck["id"], len(deck_words))
        nav.append(f'<li><a href="deck{d}-0.xhtml">{escape(deck["name"])} — {escape(deck["vi"])} ({deck["count"]})</a></li>')
        for part in range(0, len(deck_words), CARDS_PER_FILE):
            body = ""
            for i, w in enumerate(deck_words[part:part + CARDS_PER_FILE], start=part + 1):
                if w[10]:
                    pic = f"img/{Path(w[10]).stem}.jpg"
                    files.setdefault(pic, gray_jpeg(repo / "assets/img/vocab" / w[10]))
                else:
                    pic = f"emoji/{d}-{i}.png"
                    files[pic] = emoji_png(w[9], emoji_font)
                body += card(w, deck["name"], i, deck["count"], pic)
            name = f"deck{d}-{part // CARDS_PER_FILE}.xhtml"
            files[name] = xhtml(deck["name"], body).encode()
            ET.fromstring(files[name])  # self-check: well-formed XHTML or crash here
            spine.append(name)

    files["nav.xhtml"] = xhtml("Contents", f'<nav epub:type="toc"><h1>Vocabulary {len(words)}</h1><ol>{"".join(nav)}</ol></nav>').encode()
    files["style.css"] = CSS.encode()
    for i, name in enumerate(files):
        kind = {"xhtml": "application/xhtml+xml", "css": "text/css", "jpg": "image/jpeg", "png": "image/png"}[name.rsplit(".", 1)[1]]
        props = ' properties="nav"' if name == "nav.xhtml" else ""
        manifest.append(f'<item id="i{i}" href="{name}" media-type="{kind}"{props}/>')
    ids = {name: f"i{i}" for i, name in enumerate(files)}
    opf = ('<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">nvd264-vocab-3000</dc:identifier>'
           f'<dc:title>Vocabulary {len(words)} — Flashcards</dc:title><dc:creator>nvd264</dc:creator><dc:language>en</dc:language>'
           '<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata>'
           f'<manifest>{"".join(manifest)}</manifest><spine>{"".join(f"<itemref idref=\"{ids[s]}\"/>" for s in spine)}</spine></package>')

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)  # must be first, uncompressed
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", opf)
        for name, blob in files.items():
            z.writestr(f"OEBPS/{name}", blob)
    print(f"{out}: {len(words)} cards, {len(spine)} chapters, {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2 else "out/vocab-3000.epub"))
