import feedparser
from datetime import date, datetime
import os
import html
import re
import ebooklib
from ebooklib import epub
import time
import trafilatura

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

# Berapa artikel per topik
ARTICLES_PER_TOPIC = 5


def fetch_rss(url):
    """Fetch RSS feed entries."""
    try:
        d = feedparser.parse(url, agent="Mozilla/5.0")
        return [e for e in d.entries if e.get('title')]
    except Exception:
        return []


def fetch_article_content(url):
    """Scrape full article text dari URL menggunakan trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        # Extract sebagai HTML supaya boleh format dalam epub
        result = trafilatura.extract(
            downloaded,
            output_format='html',
            include_links=False,
            include_images=False,
            include_comments=False,
        )
        return result
    except Exception:
        return None


def get_rss_content(entry):
    """Fallback: ambil content dari RSS feed itself (summary/content field)."""
    # Cuba ambil full content dari feed dulu
    if 'content' in entry and entry['content']:
        return entry['content'][0].get('value', '')
    if 'summary_detail' in entry:
        return entry['summary_detail'].get('value', '')
    if 'summary' in entry:
        return entry['summary']
    return ''


def build_epub(items_by_topic):
    """Build EPUB dengan full article content dan proper TOC."""
    book = epub.EpubBook()
    book.set_identifier(f"digest-{date.today().isoformat()}")
    book.set_title(f"Daily Digest - {date.today().strftime('%d/%m/%Y')}")
    book.set_language("en")
    book.add_author("Vibe Coder")

    css_content = """
    body { font-family: serif; line-height: 1.6; margin: 1em; }
    h1 { text-align: center; border-bottom: 2px solid #333; padding-bottom: 0.5em; }
    h2 { color: #2c3e50; margin-top: 1.5em; }
    .article-source { font-style: italic; color: #7f8c8d; font-size: 0.85em; margin-bottom: 1em; }
    .article-content { text-align: justify; }
    .article-content p { margin-bottom: 0.8em; }
    .no-content { color: #999; font-style: italic; }
    hr { border: none; border-top: 1px solid #ccc; margin: 2em 0; }
    """
    style = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=css_content.encode("utf-8")
    )
    book.add_item(style)

    # Cover page
    cover = epub.EpubHtml(title='Cover', file_name='cover.xhtml', lang='en')
    cover.content = f"""
    <div style="text-align: center; padding-top: 30%;">
        <h1>Daily Digest</h1>
        <h2>{date.today().strftime('%d %B %Y')}</h2>
        <p style="color: #666; margin-top: 2em;">Kompilasi berita harian</p>
        <p style="color: #999; font-size: 0.8em;">Teknologi · AI · Isu Semasa · Kopi</p>
    </div>
    """
    cover.add_item(style)
    book.add_item(cover)

    all_chapters = []
    toc = []
    chapter_idx = 0

    for topic, articles in items_by_topic.items():
        # Topic intro page
        topic_ch = epub.EpubHtml(
            title=topic,
            file_name=f"topic_{chapter_idx:02d}.xhtml",
            lang='en'
        )
        topic_ch.content = f'<h1>{html.escape(topic)}</h1><p>{len(articles[:ARTICLES_PER_TOPIC])} artikel</p>'
        topic_ch.add_item(style)
        book.add_item(topic_ch)
        all_chapters.append(topic_ch)

        # Individual article chapters
        article_chapters = []
        for i, art in enumerate(articles[:ARTICLES_PER_TOPIC]):
            title = art.get('title', 'Untitled')
            title_safe = html.escape(title)
            link = art.get('link', '')
            source = art.get('feed_title', '')

            print(f"  Fetching: {title[:60]}...")
            content = fetch_article_content(link)

            if not content:
                content = get_rss_content(art)
            if not content:
                content = '<p class="no-content">Content tidak tersedia.</p>'

            art_ch = epub.EpubHtml(
                title=f"[{topic}] {title}",
                file_name=f"article_{chapter_idx:02d}_{i:02d}.xhtml",
                lang='en'
            )
            art_ch.content = f"""
            <h2>{title_safe}</h2>
            <p class="article-source">{html.escape(source)}</p>
            <div class="article-content">
                {content}
            </div>
            """
            art_ch.add_item(style)
            book.add_item(art_ch)
            all_chapters.append(art_ch)
            article_chapters.append(art_ch)

        # TOC: topic as section with articles nested under it
        toc.append(
            (epub.Section(topic), article_chapters)
        )
        chapter_idx += 1

    # Set TOC
    book.toc = toc

    # Add NCX and Nav
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Spine: cover first, then all chapters
    book.spine = ['nav', cover] + all_chapters

    return book


def update_index(new_entry):
    """Update index.html dengan entry baru."""
    entries = []

    if os.path.exists("index.html"):
        with open("index.html", "r") as f:
            content = f.read()
        entries = re.findall(r'<li>.*?</li>', content, re.DOTALL)

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


def update_opds_catalog(epub_name, today):
    """Generate OPDS catalog (Atom XML) supaya e-reader boleh detect."""
    BASE_URL = "https://asrulmunir.github.io/morning-digest"

    entries = []

    if os.path.exists("catalog.xml"):
        with open("catalog.xml", "r") as f:
            content = f.read()
        entries = re.findall(r'<entry>.*?</entry>', content, re.DOTALL)

    updated = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_entry = f"""<entry>
    <title>Daily Digest - {today.strftime('%d %B %Y')}</title>
    <id>urn:uuid:digest-{today.isoformat()}</id>
    <updated>{updated}</updated>
    <author><name>Vibe Coder</name></author>
    <summary>Kompilasi berita harian: Teknologi, AI, Isu Semasa, Kopi</summary>
    <link rel="http://opds-spec.org/acquisition" href="{BASE_URL}/{epub_name}" type="application/epub+zip"/>
  </entry>"""

    entries.insert(0, new_entry)
    entries_xml = "\n  ".join(entries)

    catalog = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:dc="http://purl.org/dc/terms/"
      xmlns:opds="http://opds-spec.org/2010/catalog">
  <id>urn:uuid:morning-digest-catalog</id>
  <title>Morning Digest</title>
  <subtitle>Daily news digest dalam format EPUB</subtitle>
  <updated>{updated}</updated>
  <author><name>Vibe Coder</name></author>
  <link rel="self" href="{BASE_URL}/catalog.xml" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  <link rel="start" href="{BASE_URL}/catalog.xml" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  {entries_xml}
</feed>
"""
    return catalog


if __name__ == "__main__":
    today = date.today()
    items = {}

    # 1. Fetch RSS feeds
    print("Fetching feeds...")
    for topic, urls in FEEDS.items():
        all_items = []
        for url in urls:
            feed_entries = fetch_rss(url)
            # Tag setiap entry dengan nama feed untuk reference
            feed_name = url.split('/')[2].replace('www.', '')
            for entry in feed_entries:
                entry['feed_title'] = feed_name
            all_items.extend(feed_entries)
        # Sort by date
        all_items.sort(
            key=lambda x: x.get('published_parsed') or time.gmtime(0),
            reverse=True
        )
        items[topic] = all_items

    # 2. Generate EPUB with full content
    print("Building EPUB (fetching full articles)...")
    book = build_epub(items)
    epub_name = f"Digest_{today.isoformat()}.epub"
    with open(epub_name, 'wb') as f:
        epub.write_epub(f, book)

    # 3. Update Index
    print("Updating index...")
    new_entry = f"<li><a href='{epub_name}'>{today.strftime('%d %B %Y')}</a></li>"
    with open("index.html", "w") as f:
        f.write(update_index(new_entry))

    # 4. Update OPDS Catalog
    print("Updating OPDS catalog...")
    with open("catalog.xml", "w") as f:
        f.write(update_opds_catalog(epub_name, today))

    print(f"Success! Created {epub_name}")
    print(f"OPDS feed: catalog.xml")
