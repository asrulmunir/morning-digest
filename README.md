# Morning Digest

A fully automated, serverless daily news digest that generates EPUB ebooks from RSS feeds and serves them via OPDS — readable on any e-reader.

**Zero cost. Zero maintenance. Runs entirely on GitHub Actions + GitHub Pages.**

## How It Works

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  GitHub Actions  │────▶│  generate.py  │────▶│  GitHub Pages   │
│  (cron: daily)   │     │  fetch + epub │     │  (static host)  │
└─────────────────┘     └──────────────┘     └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   E-Reader       │
                                              │   (via OPDS)     │
                                              └─────────────────┘
```

1. **GitHub Actions** runs `generate.py` on a daily schedule
2. The script fetches articles from your configured RSS feeds
3. Full article content is extracted using [trafilatura](https://github.com/adbar/trafilatura)
4. Articles are compiled into a properly structured EPUB (with TOC, chapters, cover)
5. An OPDS catalog (`catalog.xml`) is generated for e-reader discovery
6. Everything is committed back to the repo and served via GitHub Pages
7. Old digests are automatically cleaned up (configurable retention)

## Features

- **Full article content** — not just headlines, actual readable text
- **Proper EPUB structure** — cover page, table of contents, per-article chapters
- **OPDS catalog** — compatible with KOReader, Moon+ Reader, Boox, and other e-readers
- **Equal feed distribution** — round-robin across sources so no single feed dominates
- **Web admin UI** — manage feeds, settings, and trigger builds from your browser
- **Auto-cleanup** — configurable retention period (default: 7 days)
- **Content validation** — rejects scraped nav/menu junk, falls back to RSS content

## Quick Start

### 1. Fork this repo

Click **Fork** at the top of this page.

### 2. Enable GitHub Pages

Go to **Settings → Pages → Source** → select **Deploy from a branch** → choose `main` → Save.

### 3. Configure your feeds

Edit `config.json` directly on GitHub, or use the web admin UI:

```
https://<username>.github.io/<repo-name>/admin.html
```

### 4. Create a Personal Access Token

The admin UI needs a token to save config and trigger workflows:

1. Go to [GitHub Token Settings](https://github.com/settings/tokens/new?scopes=repo,workflow&description=morning-digest-admin)
2. Select scopes: `repo` + `workflow`
3. Generate and copy the token
4. Paste it in the admin UI

### 5. Connect your e-reader

Add this URL as an OPDS catalog source in your e-reader app:

```
https://<username>.github.io/<repo-name>/catalog.xml
```

## Configuration

All settings live in `config.json`:

```json
{
  "title": "Daily Digest",
  "author": "Your Name",
  "articles_per_topic": 5,
  "keep_days": 7,
  "schedule": "03:00",
  "feeds": {
    "Technology": [
      "https://www.theverge.com/rss/index.xml",
      "https://arstechnica.com/feed/"
    ],
    "Science": [
      "https://www.nature.com/nature.rss"
    ]
  }
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `title` | Book title in EPUB and OPDS | Daily Digest |
| `author` | Author name in EPUB metadata | Vibe Coder |
| `articles_per_topic` | Max articles per topic section | 5 |
| `keep_days` | Days to retain old digests | 7 |
| `schedule` | Generation time (UTC+8) | 03:00 |
| `feeds` | Topic → RSS URL mapping | — |

## Project Structure

```
├── .github/workflows/
│   └── update-digest.yml    # Daily cron job
├── admin.html               # Web UI for managing settings
├── config.json              # Feed and digest configuration
├── generate.py              # Main script: fetch → build → publish
├── catalog.xml              # OPDS feed (auto-generated)
├── index.html               # Digest listing page (auto-generated)
└── Digest_YYYY-MM-DD.epub   # Generated ebooks (auto-generated)
```

## Supported E-Readers

Tested with:
- **XTЕINK X3/X4** (built-in OPDS browser)
- **Boox** (NeoReader OPDS)
- **KOReader** (any device)
- **Moon+ Reader** (Android)

Should work with any app that supports OPDS catalogs.

## Schedule

The workflow runs daily at **3:00 AM UTC+8** (configured in `.github/workflows/update-digest.yml`). To change the schedule, adjust the cron expression:

```yaml
on:
  schedule:
    # UTC time — calculate from your timezone
    - cron: '0 19 * * *'  # 19:00 UTC = 03:00 UTC+8
```

## Limitations

- Some sites block scraping (paywalled, JS-heavy). The script falls back to RSS summary content in those cases.
- GitHub Pages has a 1GB storage limit. With auto-cleanup enabled, this is not a concern for normal use.
- GitHub Actions free tier allows 2,000 minutes/month — this workflow uses ~1 minute/day.

## License

MIT
