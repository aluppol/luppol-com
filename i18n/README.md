# Texts and languages

The site is in English and Russian. Every visible text lives in one file per language:

- `en.json`: English, the default, served at the site root (`/`)
- `ru.json`: Russian, served under `/ru/`

The page layout is the template `../src/index.html`. A template shows a text by its key: `{{people.albert.text}}` is `"people" → "albert" → "text"` in the JSON files.

## Change a text

1. Edit the value in the JSON file of that language (keep the keys identical in both files).
2. In the repository root run `python3 build.py`. It rewrites `index.html` and `ru/index.html`.
3. Commit the JSON together with the generated HTML. GitHub Pages serves the HTML as it is.

`python3 build.py --check` fails if the committed HTML is not what the sources produce; run it before pushing. If a key is missing in any language, the build stops, names the key and writes nothing.

## Inside a text

- `**bold**` makes bold text; `[text](address)` makes a link (a text must link to the same addresses in both languages).
- `\n` is a line break; `­` is a soft hyphen, a place where a long word may break on a narrow phone.
- `{{site.copyright}}` inserts another key's text.
- Texts used in the page title or meta tags must be plain; the build says so if one is not.

## Add a text or a page

Add the key to both files and use `{{key}}` in the template. A new page is a new `src/<name>.html`, served at `/<name>/` and `/ru/<name>/`. Links to this site's pages are written `{{@prefix}}/…` so that they stay in the reader's language.

## Rules

- A card mirrors the person's own site: when someone's title or description changes there, change their card here in the same language. Albert's card links to `https://albert.luppol.com{{@prefix}}/`, so the Russian hub opens his site in the same language.
- People's, product and company names stay in Latin script in every language.
