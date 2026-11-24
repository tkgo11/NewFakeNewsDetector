# NewFakeNewsDetector

[한국어](README.md) · [Design and research](docs/methodology.md)

Check one Korean or English claim against published fact checks and reference material. Results show the claim covered by each source, its original rating when available, and a link to the source.

## Run locally

Install Python 3.11 or later and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```sh
git clone https://github.com/tkgo11/NewFakeNewsDetector.git
cd NewFakeNewsDetector
uv sync --locked
uv run --locked newfakenews serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) for the Korean web interface. You can also check an English claim via the CLI.

```sh
uv run --locked newfakenews check 'Pluto was reclassified as a dwarf planet in 2006.'
```

POST JSON with a `claim` of 8 to 500 characters to `/api/v1/check`. Optional fields are `language` (`auto`, `ko`, or `en`) and `online` (a boolean that defaults to `false`). The schema is served at `/openapi.json`.

Set `GOOGLE_FACTCHECK_API_KEY` to enable Google Fact Check Tools, then choose online lookup in the web form, add `--online` in the CLI, or set `"online": true` via the API. This sends the submitted claim and language to Google. The included sample catalog works offline and covers ten claim texts. Add a JSON catalog using `FAKENEWS_CATALOG`. For the format, see the [bundled catalog](src/newfakenewsdetector/data/catalog.json).

For Chrome, load the `extension` directory as an unpacked extension in `chrome://extensions`. With the app running on its default port, select a sentence, open the context menu, and choose NewFakeNewsDetector. The app fills the form for review before submitting.

The app abstains when a source does not cover the exact claim. It works with text and a limited collection of previously documented claims. Read the cited material for the date, scope, and caveats.

Run the checks with `uv run --locked pytest`, `uv run --locked ruff check .`, and `uv run --locked ruff format --check .`.

[MIT license](LICENSE)
