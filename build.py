#!/usr/bin/env python3
"""Build this site's English and Russian pages.

    python3 build.py           write the pages
    python3 build.py --check   exit 1 if the committed pages differ from what the sources produce

Sources: src/*.html (one template per page) and i18n/<lang>.json (every visible text, by key).
English is written at the site root (index.html, projects/index.html, ...), Russian under ru/.
Python 3 standard library only. Editing guide: i18n/README.md.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
I18N = ROOT / "i18n"
LANGS = ("en", "ru")  # order of the flags; the first one is the default, served at the root
BASE = "https://" + (ROOT / "CNAME").read_text(encoding="utf-8").strip()

PLACEHOLDER = re.compile(r"\{\{\s*(@?[A-Za-z0-9_.-]+)\s*\}\}")
LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
MARKUP = re.compile(r"\*\*|\[[^\]\n]+\]\([^)\s]+\)|\n")
VALUE_VARS = ("@lang", "@prefix", "@demo")
PAGE_VARS = VALUE_VARS + ("@alternates", "@switcher")
SWITCHER_KEYS = ("language.name", "language.switcher")


def _us_flag():
    hoist, fly = 26, 39  # 13 stripes of 2 units, drawn at 3:2
    canton_w, canton_h = 0.76 * hoist, 14  # canton over the top 7 stripes, official width
    step_x, step_y = canton_w / 12, canton_h / 10  # 50 stars: 9 rows of 6 and 5

    def num(x):
        return f"{x:.3f}".rstrip("0").rstrip(".")

    stripes = "".join("M0 0h39v2H0z" if i == 0 else "m0 4h39v2H0z" for i in range(7))
    row6 = "".join(f'<use href="#flag-us-s" x="{num(step_x * k)}"/>' for k in (1, 3, 5, 7, 9, 11))
    row5 = "".join(f'<use href="#flag-us-s" x="{num(step_x * k)}"/>' for k in (2, 4, 6, 8, 10))
    rows = "".join(
        f'<use href="#flag-us-r{6 if r % 2 else 5}" y="{num(step_y * r)}"/>' for r in range(1, 10)
    )
    return (
        f'<svg class="flag" viewBox="0 0 {fly} {hoist}" width="24" height="16" aria-hidden="true" focusable="false">'
        f'<path fill="#fff" d="M0 0h{fly}v{hoist}H0z"/>'
        f'<path fill="#b22234" d="{stripes}"/>'
        f'<path fill="#3c3b6e" d="M0 0h{num(canton_w)}v{canton_h}H0z"/>'
        '<defs><path id="flag-us-s" fill="#fff" d="M0-.8l.47 1.447-1.231-.894h1.522l-1.231.894z"/>'
        f'<g id="flag-us-r6">{row6}</g><g id="flag-us-r5">{row5}</g></defs>'
        f"{rows}</svg>"
    )


def _tricolour(top, middle, bottom):
    return (
        '<svg class="flag" viewBox="0 0 9 6" width="24" height="16" aria-hidden="true" focusable="false">'
        f'<path fill="{top}" d="M0 0h9v2H0z"/><path fill="{middle}" d="M0 2h9v2H0z"/>'
        f'<path fill="{bottom}" d="M0 4h9v2H0z"/></svg>'
    )


FLAGS = {
    "en": _us_flag(),
    "ru": _tricolour("#fff", "#0039a6", "#d52b1e"),
}


class BuildError(Exception):
    pass


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def prefix(lang):
    return "" if lang == LANGS[0] else "/" + lang


def page_vars(lang, path, strings):
    return {
        "@lang": lang,
        "@prefix": prefix(lang),
        "@demo": "" if lang == LANGS[0] else "?lang=" + lang,
        "@alternates": alternates(path),
        "@switcher": switcher(lang, path, strings),
    }


def alternates(path):
    lines = [f'<link rel="alternate" hreflang="{lang}" href="{BASE}{prefix(lang)}{path}">' for lang in LANGS]
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{BASE}{path}">')
    return "\n".join(lines)


def switcher(current, path, strings):
    lines = [f'<nav class="lang" aria-label="{escape(strings[current]["language.switcher"])}">']
    for lang in LANGS:
        name = escape(strings[lang]["language.name"])
        mark = ' aria-current="true"' if lang == current else ""
        lines.append(
            f'  <a href="{prefix(lang)}{path}" hreflang="{lang}" lang="{lang}" title="{name}"{mark}>'
            f'{FLAGS[lang]}<span class="visually-hidden">{name}</span></a>'
        )
    lines.append("</nav>")
    return "\n".join(lines)


def load_language(lang):
    path = I18N / f"{lang}.json"

    def no_duplicates(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise BuildError(f"{path.relative_to(ROOT)}: key '{key}' appears twice in the same object")
            seen[key] = value
        return seen

    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    except FileNotFoundError:
        raise BuildError(f"{path.relative_to(ROOT)} is missing") from None
    except json.JSONDecodeError as err:
        raise BuildError(f"{path.relative_to(ROOT)}: invalid JSON, line {err.lineno} column {err.colno}: {err.msg}") from None

    flat = {}

    def walk(node, trail):
        for key, value in node.items():
            name = f"{trail}.{key}" if trail else key
            if isinstance(value, dict):
                walk(value, name)
            elif isinstance(value, str):
                if not value.strip():
                    raise BuildError(f"{path.relative_to(ROOT)}: '{name}' is empty")
                flat[name] = value
            else:
                raise BuildError(f"{path.relative_to(ROOT)}: '{name}' must be text or a group of texts")

    walk(data, "")
    return flat


def expand(lang, key, strings, chain=()):
    """The text of a key with {{other.key}} references inside it filled in (same language)."""
    if key in chain:
        raise BuildError(f"i18n/{lang}.json: '{key}' refers to itself through {' -> '.join(chain + (key,))}")
    if key not in strings[lang]:
        raise BuildError(f"i18n/{lang}.json: missing key '{key}' (used by '{chain[-1]}')" if chain else f"i18n/{lang}.json: missing key '{key}'")

    def fill(match):
        name = match.group(1)
        if name in VALUE_VARS:
            return match.group(0)
        if name.startswith("@"):
            raise BuildError(f"i18n/{lang}.json: '{key}' uses {name}, which only templates may use")
        return expand(lang, name, strings, chain + (key,))

    return PLACEHOLDER.sub(fill, strings[lang][key])


def to_html(text):
    out = escape(text)
    out = LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', out)
    out = BOLD.sub(r"<strong>\1</strong>", out)
    return out.replace("\n", "<br>")


def plain_context(template, pos):
    """True inside a tag (an attribute) or inside <title>: only plain text may go there."""
    before = template[:pos]
    if before.rfind("<") > before.rfind(">"):
        return True
    return before.rfind("<title>") > before.rfind("</title>")


def render(template, name, lang, path, strings):
    variables = page_vars(lang, path, strings)

    def fill_vars(text):
        return PLACEHOLDER.sub(lambda m: variables[m.group(1)] if m.group(1) in VALUE_VARS else m.group(0), text)

    def fill(match):
        key = match.group(1)
        if key.startswith("@"):
            if key not in variables:
                raise BuildError(f"src/{name}: unknown variable {key}")
            value = variables[key]
            if "\n" in value:  # keep the indentation of the line the placeholder sits on
                line_start = template.rfind("\n", 0, match.start()) + 1
                indent = template[line_start:match.start()]
                if not indent.strip():
                    value = value.replace("\n", "\n" + indent)
            return value
        text = fill_vars(expand(lang, key, strings))
        if plain_context(template, match.start()):
            if MARKUP.search(text):
                raise BuildError(
                    f"i18n/{lang}.json: '{key}' goes into an attribute or <title> in src/{name}, "
                    "so it must be plain text (no **bold**, [links](...) or line breaks)"
                )
            return escape(text)
        return to_html(text)

    return PLACEHOLDER.sub(fill, template)


def pages():
    found = sorted(p for p in SRC.glob("*.html") if not p.name.startswith("_"))
    if not found:
        raise BuildError("src/ has no page templates")
    for template in found:
        slug = "" if template.stem == "index" else template.stem + "/"
        yield template, "/" + slug


def output_path(lang, path):
    return ROOT / prefix(lang).lstrip("/") / path.lstrip("/") / "index.html"


def build():
    strings = {lang: load_language(lang) for lang in LANGS}
    errors, warnings = [], []

    every_key = set().union(*strings.values())
    for lang in LANGS:
        for key in sorted(every_key - strings[lang].keys()):
            others = ", ".join(f"{other}.json" for other in LANGS if key in strings[other])
            errors.append(f"i18n/{lang}.json: missing key '{key}' (present in {others})")

    used = set(SWITCHER_KEYS)
    templates = []
    for template, path in pages():
        text = template.read_text(encoding="utf-8")
        templates.append((template.name, path, text))
        for key in PLACEHOLDER.findall(text):
            if key.startswith("@"):
                if key not in PAGE_VARS:
                    errors.append(f"src/{template.name}: unknown variable {key}")
            else:
                used.add(key)
    for key in sorted(used - every_key):
        errors.append(f"missing key '{key}' in every language file (used by the templates)")

    # nested references, and links that must point to the same places in every language
    for key in sorted(every_key):
        for lang in LANGS:
            if key in strings[lang]:
                try:
                    expand(lang, key, strings)
                except BuildError as err:
                    errors.append(str(err))
                used.update(name for name in PLACEHOLDER.findall(strings[lang][key]) if not name.startswith("@"))
        targets = {lang: sorted(href for _, href in LINK.findall(strings[lang].get(key, ""))) for lang in LANGS}
        for lang in LANGS[1:]:
            if key in strings[lang] and key in strings[LANGS[0]] and targets[lang] != targets[LANGS[0]]:
                errors.append(f"i18n/{lang}.json: '{key}' must link to the same addresses as in {LANGS[0]}.json")
    for key in sorted(every_key - used):
        warnings.append(f"key '{key}' is not used by any page")

    if errors:
        raise BuildError("\n".join(dict.fromkeys(errors)))

    outputs = {}
    for name, path, text in templates:
        for lang in LANGS:
            outputs[output_path(lang, path)] = render(text, name, lang, path, strings)
    return outputs, warnings


def stray_pages(outputs):
    stray = []
    for lang in LANGS[1:]:
        folder = ROOT / lang
        if folder.is_dir():
            stray += [p for p in folder.rglob("*.html") if p not in outputs]
    return sorted(stray)


def main(argv):
    check = "--check" in argv[1:]
    unknown = [arg for arg in argv[1:] if arg != "--check"]
    if unknown:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        outputs, warnings = build()
    except BuildError as err:
        print("build.py: stopped, nothing was written.\n" + str(err), file=sys.stderr)
        return 1
    for warning in warnings:
        print("build.py: warning: " + warning, file=sys.stderr)

    stray = stray_pages(outputs)
    if check:
        stale = [p for p, html in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != html]
        for p in stale:
            print(f"build.py --check: {p.relative_to(ROOT)} is not what the sources produce", file=sys.stderr)
        for p in stray:
            print(f"build.py --check: {p.relative_to(ROOT)} is not produced by any source", file=sys.stderr)
        if stale or stray:
            print("Run: python3 build.py", file=sys.stderr)
            return 1
        print(f"build.py --check: all {len(outputs)} pages match the sources")
        return 0

    written = 0
    for p, html in outputs.items():
        if not p.exists() or p.read_text(encoding="utf-8") != html:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(html, encoding="utf-8")
            written += 1
    for p in stray:
        print(f"build.py: warning: {p.relative_to(ROOT)} is not produced by any source; delete it if it is stale", file=sys.stderr)
    print(f"build.py: {len(outputs)} pages, {written} written, {len(outputs) - written} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
