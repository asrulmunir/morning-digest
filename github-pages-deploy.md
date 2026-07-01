# Panduan Deployment: Daily Digest ke GitHub Pages (Serverless)

Projek ini adalah migrasi sistem `morning-digest` anda dari VPS (Raspberry Pi) ke hosting **Serverless (GitHub Pages)**.

**Kenapa GitHub Pages?**
1.  **Percuma 100%** (1GB storage cukup untuk ribuan eBook).
2.  **OPDS Native:** Boleh connect terus ke app E-reader (Moon+, Boox, Kobo) tanpa server dinamik.
3.  **Maintenance-Free:** Tak perlu update OS, tak perlu risau server down.

**Cara Kerja:**
1.  **GitHub Actions** (Backend) akan generate file `.epub` setiap pagi pukul 3:00 AM (MYT).
2.  **GitHub Pages** (Frontend) akan serve folder tu sebagai website.
3.  E-reader fetch file tu dari internet.

---

## 1. Struktur Fail (File Tree)

Anda perlu create repository baru di GitHub (contoh: `morning-digest`), kemudian upload fail-fail ni:

```
morning-digest/
├── .github/
│   └── workflows/
│       └── update-digest.yml  <-- Script Automasi
├── assets/
│   ├── style.css              <-- Styling buku
│   └── cover.png              <-- (Optional) Gambar cover
├── generate.py                <-- Script Python logic
├── README.md
└── index.html                 <-- (Auto-generated nanti, jangan upload manual)
```

---

## 2. Kod Sumber (Copy-Paste Ke GitHub)

### Fail 1: `generate.py` (Logic Utama)
Script ni akan fetch berita, compile jadi buku, dan update senarai (index).

```python
import feedparser
from datetime import date
import os
import html
import re
import ebooklib
from ebooklib import epub
import time

# === KONFIGURASI (BETULKAN SINI) ===
FEEDS = {
    "Teknologi": [
        "https://www.theverge.com/rss/index.xml",
        "https://bgr.com/feed/",
        "https://www.macrumors.com/macrumors.xml"
    ],
    "AI & ML": [
        "https://www.artificialintelligence-news.com/feed/"
    ],
    "Isu Semasa": [
        "https://www.hmetro.com.my/feed/",
        "https://www.nst.com.my/news/nation",
        "https://www.saharonline.my/feed/"
    ],
    "Kopi": [
        "https://www.perfectdailygrind.com/feed/"
    ]
}

def fetch_rss(url):
    try:
        d = feedparser.parse(url, agent="Mozilla/5.0")
        return [e for e in d.entries if e.get('title')]
    except:
        return []

def build_epub(items_by_topic):
    book = epub.EpubBook()
    book.set_identifier(f"digest-{date.today().isoformat()}")
    book.set_title(f"Daily Digest - {date.today().strftime('%d/%m/%Y')}")
    book.set_language("en")
    book.add_author("Vibe Coder")

    # CSS — add sekali sahaja pada buku
    css_content = """
    body { font-family: serif; line-height: 1.5; }
    h1 { text-align: center; border-bottom: 2px solid #333; }
    h2 { color: #2c3e50; border-bottom: 1px solid #ddd; }
    p.source { font-style: italic; color: #7f8c8d; font-size: 0.9em; }
    """
    style = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=css_content.encode("utf-8"))
    book.add_item(style)

    nav = epub.EpubNav()
    book.add_item(nav)

    chapters = []
    for topic, articles in items_by_topic.items():
        ch = epub.EpubHtml(title=topic, file_name=f"{topic.lower().replace(' ', '_').replace('&', 'and')}.xhtml", lang='en')
        ch.content = f'<h1>{topic}</h1><ul>'

        for art in articles[:5]:  # Top 5 only
            title = html.escape(art.get('title', ''))
            link = art.get('link', '')
            ch.content += f'<li><a href="{link}">{title}</a></li>'

        ch.content += '</ul>'
        ch.add_item(style)  # Reference stylesheet, bukan add baru
        book.add_item(ch)
        chapters.append(ch)

    book.spine = ['nav'] + chapters
    return book

def update_index(new_entry):
    """Update index.html dengan entry baru. Parse secara robust."""
    entries = []

    if os.path.exists("index.html"):
        with open("index.html", "r") as f:
            content = f.read()
        # Extract semua <li>...</li> sedia ada
        import re
        entries = re.findall(r'<li>.*?</li>', content, re.DOTALL)

    # Prepend entry baru
    entries.insert(0, new_entry)

    entries_html = "\n        ".join(entries)
    return f"""<!DOCTYPE html>
<html>
<head><title>Daily Digest</title></head>
<body>
    <h1>Latest Digests</h1>
    <ul>
        {entries_html}
    </ul>
</body>
</html>
"""

if __name__ == "__main__":
    today = date.today()
    items = {}

    # 1. Fetch Data
    print("Fetching feeds...")
    for topic, urls in FEEDS.items():
        all_items = []
        for url in urls:
            all_items.extend(fetch_rss(url))
        # Sort by date — fallback ke time.struct_time kosong jika tiada published_parsed
        all_items.sort(
            key=lambda x: x.get('published_parsed') or time.gmtime(0),
            reverse=True
        )
        items[topic] = all_items

    # 2. Generate EPUB
    print("Building EPUB...")
    book = build_epub(items)
    epub_name = f"Digest_{today.isoformat()}.epub"
    with open(epub_name, 'wb') as f:
        epub.write_epub(f, book)

    # 3. Update Index for E-Reader
    print("Updating index...")
    new_entry = f"<li><a href='{epub_name}'>{today.strftime('%d %B %Y')}</a></li>"

    with open("index.html", "w") as f:
        f.write(update_index(new_entry))

    print(f"Success! Created {epub_name}")
```

---

### Fail 2: `.github/workflows/update-digest.yml` (Jadual Automatik)
Fail ni yang buat "magic". Dia akan run script Python kat atas setiap pagi secara automatik.

```yaml
name: Daily Digest Generator

on:
  schedule:
    # Run pukul 3:00 AM MYT (UTC+8) = 7:00 PM UTC hari sebelumnya
    - cron: '0 19 * * *'
  workflow_dispatch: # Boleh run manual dari GitHub UI

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          pip install feedparser ebooklib

      - name: Generate Digest
        run: python generate.py

      - name: Commit & Push
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add .
          git commit -m "Update daily digest for $(date +%Y-%m-%d)" || exit 0
          git push
```

---

## 3. Cara Setup (Langkah Demi Langkah)

1.  **GitHub Account:** Log in ke [github.com](https://github.com).
2.  **New Repository:** Create repository baru (nama apa saja, contoh `my-digest`).
3.  **Upload Files:**
    *   Upload `generate.py`.
    *   Upload folder `.github/workflows/` (dengan fail `update-digest.yml` di dalam).
4.  **Settings (Penting!):**
    *   Pergi ke **Settings > Pages**.
    *   Di bawah **Source**, pilih **Deploy from a branch**.
    *   Pilih **main** branch.
    *   Save.
5.  **Wait:** Tunggu 3-5 minit. Refresh page tu, akan ada notifikasi hijau "Your site is live".

---

## 4. Cara Connect ke E-Reader

Sekarang E-reader anda boleh baca terus dari internet:

1.  Buka App Reader (contoh: Moon+ Reader, ReadEra, atau Kindle browser).
2.  Pilih **Add Library / New Source**.
3.  Masukkan URL:
    `https://<username>.github.io/<repo-name>/`
    *(Contoh: `https://abumuaaz.github.io/my-digest/`)*
4.  Tekan Enter. App akan detect semua file `.epub` yang ada.

---

## 5. Troubleshooting

Jika ada error, cek ni:
*   **"403 Forbidden":** Pastikan repository tu **Public**.
*   **"Build Failed":** Cek tab **Actions** dekat GitHub, tengok log error dia. Usually sebab library `ebooklib` tak install.
*   **"Storage Full":** Repository ada limit 1GB. Script ni simpan history semua buku. Kalau penuh, delete file `.epub` lama yang tak perlu.
