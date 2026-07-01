import feedparser
from datetime import date, datetime
import os
import html
import re
import json
import ebooklib
from ebooklib import epub
import time
import trafilatura

# === LOAD CONFIG ===
with open('config.json', 'r') as f:
    CONFIG = json.load(f)

FEEDS = CONFIG['feeds']
ARTICLES_PER_TOPIC = CONFIG.get('articles_per_topic', 5)
KEEP_DAYS = CONFIG.get('keep_days', 7)
BOOK_TITLE = CONFIG.get('title', 'Daily Digest')
BOOK_AUTHOR = CONFIG.get('author', 'Vibe Coder')


def fetch_rss(url):
    """Fetch RSS feed entries from a given URL."""
    try:
        d = feedparser.parse(url, agent="Mozilla/5.0")
        return [e for e in d.entries if e.get('title')]
    except Exception:
        return []


def fetch_article_content(url):
    """Scrape full article text from a URL using trafilatura.

    Returns HTML content if successful, None otherwise.
    Validates extracted content to reject navigation/menu junk.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        result = trafilatura.extract(
            downloaded,
            output_format='html',
            include_links=False,
            include_images=False,
            include_comments=False,
        )
        if not result:
            return None
        # Validate — reject if content looks like nav/menu junk
        text_only = re.sub(r'<[^>]+>', '', result).strip()
        lines = [l.strip() for l in text_only.split('\n') if l.strip()]
        avg_line_length = sum(len(l) for l in lines) / max(len(lines), 1)
        # Nav/menu typically has many short lines
        if avg_line_length < 20 and len(lines) > 10:
            return None
        # Reject if total content is too short (< 200 chars)
        if len(text_only) < 200:
            return None
        return result
    except Exception:
        return None


def get_rss_content(entry):
    """Fallback: extract content from the RSS feed entry itself."""
    content = ''
    if 'content' in entry and entry['content']:
        content = entry['content'][0].get('value', '')
    elif 'summary_detail' in entry:
        content = entry['summary_detail'].get('value', '')
    elif 'summary' in entry:
        content = entry['summary']

    if not content:
        return ''

    # Clean up — remove script/style tags but keep HTML structure
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)

    # Reject if content is too short to be useful
    text_only = re.sub(r'<[^>]+>', '', content).strip()
    if len(text_only) < 50:
        return ''

    return content


def build_epub(items_by_topic):
    """Build a proper EPUB with full article content, cover page, and TOC."""
    book = epub.EpubBook()
    book.set_identifier(f"digest-{date.today().isoformat()}")
    book.set_title(f"{BOOK_TITLE} - {date.today().strftime('%d/%m/%Y')}")
    book.set_language("en")
    book.add_author(BOOK_AUTHOR)

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
        <h1>{BOOK_TITLE}</h1>
        <h2>{date.today().strftime('%d %B %Y')}</h2>
        <p style="color: #666; margin-top: 2em;">Daily news compilation</p>
        <p style="color: #999; font-size: 0.8em;">{' · '.join(FEEDS.keys())}</p>
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
        article_count = len(articles[:ARTICLES_PER_TOPIC])
        topic_ch.content = f'<h1>{html.escape(topic)}</h1><p>{article_count} article{"s" if article_count != 1 else ""}</p>'
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
                content = '<p class="no-content">Content not available.</p>'

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

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav', cover] + all_chapters

    return book


def update_index(new_entry):
    """Update index.html with a new digest entry."""
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


if __name__ == "__main__":
    # Use UTC+8 (MYT) for date so filename matches local date
    from datetime import timezone, timedelta
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).date()
    items = {}

    # 1. Fetch RSS feeds
    print("Fetching feeds...")
    for topic, urls in FEEDS.items():
        all_items = []
        for url in urls:
            feed_entries = fetch_rss(url)
            # Tag each entry with feed name and source URL
            feed_name = url.split('/')[2].replace('www.', '')
            for entry in feed_entries:
                entry['feed_title'] = feed_name
                entry['feed_url'] = url
            all_items.extend(feed_entries)

        # Distribute articles equally across feeds (round-robin)
        feeds_grouped = {}
        for item in all_items:
            src = item['feed_url']
            if src not in feeds_grouped:
                feeds_grouped[src] = []
            feeds_grouped[src].append(item)

        # Sort each feed by date (newest first)
        for src in feeds_grouped:
            feeds_grouped[src].sort(
                key=lambda x: x.get('published_parsed') or time.gmtime(0),
                reverse=True
            )

        # Round-robin pick to ensure equal representation
        distributed = []
        max_per_feed = max(1, ARTICLES_PER_TOPIC // max(len(feeds_grouped), 1))
        remainder = ARTICLES_PER_TOPIC - (max_per_feed * len(feeds_grouped))

        for i, src in enumerate(feeds_grouped):
            count = max_per_feed + (1 if i < remainder else 0)
            distributed.extend(feeds_grouped[src][:count])

        # Final sort by date
        distributed.sort(
            key=lambda x: x.get('published_parsed') or time.gmtime(0),
            reverse=True
        )
        items[topic] = distributed

    # 2. Generate EPUB with full content
    print("Building EPUB (fetching full articles)...")
    book = build_epub(items)
    epub_name = f"Digest_{today.isoformat()}.epub"
    with open(epub_name, 'wb') as f:
        epub.write_epub(f, book)

    # 3. Update index page
    print("Updating index...")
    new_entry = f"<li><a href='{epub_name}'>{today.strftime('%d %B %Y')}</a></li>"
    with open("index.html", "w") as f:
        f.write(update_index(new_entry))

    # 4. Cleanup — delete epubs older than KEEP_DAYS, rebuild index + catalog
    print(f"Cleaning up old digests (keeping {KEEP_DAYS} days)...")
    cutoff = today - __import__('datetime').timedelta(days=KEEP_DAYS)
    for f in os.listdir('.'):
        if f.startswith('Digest_') and f.endswith('.epub'):
            try:
                file_date = date.fromisoformat(f.replace('Digest_', '').replace('.epub', ''))
                if file_date < cutoff:
                    os.remove(f)
                    print(f"  Deleted: {f}")
            except ValueError:
                continue

    # Rebuild index.html and catalog.xml to reflect existing files only
    existing_epubs = sorted(
        [f for f in os.listdir('.') if f.startswith('Digest_') and f.endswith('.epub')],
        reverse=True
    )

    # Rebuild index
    entries_html = "\n        ".join(
        f"<li><a href='{f}'>{date.fromisoformat(f.replace('Digest_', '').replace('.epub', '')).strftime('%d %B %Y')}</a></li>"
        for f in existing_epubs
    )
    with open("index.html", "w") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head><title>Daily Digest</title></head>
<body>
    <h1>Latest Digests</h1>
    <ul>
        {entries_html}
    </ul>
</body>
</html>
""")

    # Rebuild OPDS catalog
    BASE_URL = "https://asrulmunir.github.io/morning-digest"
    updated = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    opds_entries = []
    for f in existing_epubs:
        file_date = date.fromisoformat(f.replace('Digest_', '').replace('.epub', ''))
        opds_entries.append(f"""<entry>
    <title>{html.escape(BOOK_TITLE)} - {file_date.strftime('%d %B %Y')}</title>
    <id>urn:uuid:digest-{file_date.isoformat()}</id>
    <updated>{updated}</updated>
    <author><name>{html.escape(BOOK_AUTHOR)}</name></author>
    <summary>Daily news compilation: {html.escape(', '.join(FEEDS.keys()))}</summary>
    <link rel="http://opds-spec.org/acquisition" href="{BASE_URL}/{f}" type="application/epub+zip"/>
  </entry>""")

    with open("catalog.xml", "w") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:dc="http://purl.org/dc/terms/"
      xmlns:opds="http://opds-spec.org/2010/catalog">
  <id>urn:uuid:morning-digest-catalog</id>
  <title>{html.escape(BOOK_TITLE)}</title>
  <subtitle>Daily news digest in EPUB format</subtitle>
  <updated>{updated}</updated>
  <author><name>{html.escape(BOOK_AUTHOR)}</name></author>
  <link rel="self" href="{BASE_URL}/catalog.xml" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  <link rel="start" href="{BASE_URL}/catalog.xml" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
  {chr(10).join(opds_entries)}
</feed>
""")

    print(f"Done! Created {epub_name}")
    print(f"Keeping {len(existing_epubs)} digest(s) (last {KEEP_DAYS} days)")
    print(f"OPDS feed: catalog.xml")
