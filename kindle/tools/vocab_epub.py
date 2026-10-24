#!/usr/bin/env python3
"""Turn the interview repo's vocab.js into a flashcard EPUB for KOReader.

Usage: vocab_epub.py <path/to/interview> [out.epub]
Each word becomes two pages: front (picture, word, IPA) and back (meaning, examples).
"""
import io
import json
import sys
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from epub import write_epub, xhtml

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

    files, spine, nav = {}, [], []
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
            files[name] = xhtml(deck["name"], body)
            spine.append(name)

    files["style.css"] = CSS.encode()
    write_epub(out, "nvd264-vocab-3000", f"Vocabulary {len(words)} — Flashcards", files, spine, f'<ol>{"".join(nav)}</ol>')


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2 else "out/vocab-3000.epub"))
