#!/usr/bin/env python3
"""Turn the interview Study Hub's built HTML pages into one EPUB for KOReader.

Usage: site_epub.py <path/to/interview> [out.epub]
Uses the pages tools/build.mjs already generated, so run `npm run build` there first if the Markdown changed.
"""
import re
import subprocess
import sys
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup

from epub import write_epub, xhtml

SECTIONS = {"interview-prep": "Interview Prep", "system-design": "System Design",
            "dsa": "DSA Patterns", "english-lessons": "English Lessons"}
# parts that only work with the site's JavaScript
DROP = ".toolbar, .page-stats, .no-results, .pager, .tts, .viz, .qa-foot, .code-head, .callout-icon, button, input, script"
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")  # KOReader has no emoji font
# match whole inline <svg> elements; parsing them with an HTML parser would lowercase viewBox etc.
SVG = re.compile(r"<svg\b.*?</svg>", re.S)
SVG_OPEN = re.compile(r"""<svg\b(?:[^>"']|"[^"]*"|'[^']*')*>""")

CSS = """
body { font-family: serif; }
h1 { font-size: 1.6em; margin-bottom: 0.2em; }
.eyebrow { font-size: 0.8em; color: #555; }
.lead { font-style: italic; }
h2 { font-size: 1.3em; border-bottom: 1px solid #000; margin-top: 1.5em; }
.sec-num, .qa-num { margin-right: 0.4em; }
h3 { font-size: 1.1em; margin: 1.4em 0 0.4em; }
.chip { font-size: 0.65em; font-weight: normal; border: 1px solid #666; padding: 0 0.25em; margin-left: 0.3em; }
pre { white-space: pre-wrap; font-family: monospace; font-size: 0.72em; background: #eee; padding: 0.4em; }
code { font-family: monospace; }
table { border-collapse: collapse; font-size: 0.8em; margin: 0.5em 0; }
th, td { border: 1px solid #888; padding: 0.15em 0.3em; }
.callout { border-left: 3px solid #000; padding-left: 0.6em; margin: 0.8em 0; }
.callout-title { font-weight: bold; }
figure { margin: 0.8em 0; text-align: center; }
img.diagram { max-width: 100%; }
figcaption { font-size: 0.8em; color: #555; }
"""


def diagram_css(repo):
    """The site's .dg-* SVG rules with light-theme colours inlined (librsvg can't see the page stylesheet)."""
    css = (repo / "assets/css/style.css").read_text(encoding="utf-8")
    root = css[css.index(":root"):]
    colours = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", root[:root.index("}")]))
    rules = "".join(re.findall(r"\.dg-[^{}]*\{[^}]*\}", css))
    while "var(" in rules:
        rules = re.sub(r"var\((--[\w-]+)\)", lambda m: colours[m[1]], rules)
    return "svg { font-family: sans-serif; } " + rules


def svg_png(svg, css):
    head = SVG_OPEN.match(svg).end()
    svg = svg[:head] + f"<style>{css}</style>" + svg[head:]
    png = subprocess.run(["rsvg-convert", "-z", "2"], input=svg.encode(), capture_output=True, check=True).stdout
    return subprocess.run(["magick", "png:-", "-background", "white", "-flatten", "-colorspace", "Gray", "png:-"],
                          input=png, capture_output=True, check=True).stdout


def chapter(repo, page, css, files, chapters):
    def to_img(m):
        name = f"img/{len(files)}.png"
        files[name] = svg_png(m[0], css)
        return f'<img class="diagram" src="{name}" alt=""/>'

    raw = page.read_text(encoding="utf-8")
    raw = raw[raw.index("<main"):raw.index("</main>") + 7]  # skip the site chrome and its icon SVGs
    main = BeautifulSoup(SVG.sub(to_img, raw), "html.parser").find("main")
    for el in main.select(DROP):
        el.decompose()
    for d in main.select("details"):  # open every card and hint: there is nothing to click on e-ink
        d.name = "div"
        d.attrs.pop("open", None)
        d.find("summary").name = "h3" if "qa" in d["class"] else "div"
    for a in main.find_all("a", href=True):
        path, _, frag = a["href"].partition("#")
        if not path or a["href"].startswith(("http://", "https://")):
            continue
        target = chapters.get((page.parent / path).resolve())
        if target:
            a["href"] = target + (f"#{frag}" if frag else "")
        else:
            a.unwrap()
    sections = [(s["id"], s.find("h2").get_text(" ", strip=True)) for s in main.select("section[id]") if s.find("h2")]
    return main.find("h1").get_text(" ", strip=True), EMOJI.sub("", main.decode_contents()), sections


def build(repo, out):
    pages = [p for d in SECTIONS for p in sorted((repo / d).glob("[0-9][0-9]-*.html"))]
    chapters = {p.resolve(): f"{p.parent.name}-{p.stem}.xhtml" for p in pages}
    css, files, nav = diagram_css(repo), {}, ""
    for d, label in SECTIONS.items():
        items = ""
        for page in (p for p in pages if p.parent.name == d):
            name = chapters[page.resolve()]
            title, body, sections = chapter(repo, page, css, files, chapters)
            files[name] = xhtml(title, body)
            subs = "".join(f'<li><a href="{name}#{sid}">{escape(EMOJI.sub("", t))}</a></li>' for sid, t in sections)
            items += f'<li><a href="{name}">{escape(EMOJI.sub("", title))}</a>' + (f"<ol>{subs}</ol>" if subs else "") + "</li>"
        first = next(chapters[p.resolve()] for p in pages if p.parent.name == d)
        nav += f'<li><a href="{first}">{escape(label)}</a><ol>{items}</ol></li>'
    files["style.css"] = CSS.encode()
    spine = [chapters[p.resolve()] for p in pages]
    write_epub(out, "nvd264-study-hub", "Study Hub — Interview Prep", files, spine, f"<ol>{nav}</ol>")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2 else "out/study-hub.epub"))
