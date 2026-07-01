import feedparser
from datetime import date
import os
import html
import re
import ebooklib
from ebooklib import epub
import time

# === KONFIGURASI ===
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
    except Exception:
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
    style = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=css_content.encode("utf-8")
    )
    book.add_item(style)

    nav = epub.EpubNav()
    book.add_item(nav)

    chapters = []
    for topic, articles in items_by_topic.items():
        ch = epub.EpubHtml(
            title=topic,
            file_name=f"{topic.lower().replace(' ', '_').replace('&', 'and')}.xhtml",
            lang='en'
        )
        ch.content = f'<h1>{topic}</h1><ul>'

        for art in articles[:5]:  # Top 5 only
            title = html.escape(art.get('title', ''))
            link = art.get('link', '')
            ch.content += f'<li><a href="{link}">{title}</a></li>'

        ch.content += '</ul>'
        ch.add_item(style)  # Reference stylesheet
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
        # Sort by date — fallback ke epoch jika tiada published_parsed
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
