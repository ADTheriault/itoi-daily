#!/usr/bin/env python3
"""
Itoi Daily Essay Scraper & Translator

Scrapes Shigesato Itoi's daily essay from 1101.com,
translates it via Claude API, and updates an RSS feed.
"""

import os
import re
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from anthropic import Anthropic
from feedgen.feed import FeedGenerator


# Configuration
ESSAY_URL = "https://www.1101.com/"
OUTPUT_DIR = Path(__file__).parent / "docs"
FEED_FILE = OUTPUT_DIR / "feed.xml"
ARCHIVE_FILE = OUTPUT_DIR / "archive.json"
DARLING_IMAGE_URL = "https://www.1101.com/home/2025/images/home/darling.png"


def scrape_essay() -> dict | None:
    """Fetch and extract Itoi's daily essay from 1101.com using Playwright."""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(ESSAY_URL)
        page.wait_for_timeout(2000)  # Wait for JS to render

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, 'html.parser')

    title = None
    author = None
    body = None

    # Strategy 1: Use specific selectors (like hellodarling)
    title_el = soup.select_one("div.darling-title h2")
    author_el = soup.select_one("div.darling-title h3")
    body_el = soup.select_one("div.darling-text")

    if title_el and title_el.get_text(strip=True):
        title = title_el.get_text(strip=True)
    else:
        # Fallback: extract title from x-data attribute
        darling_div = soup.select_one("div.darling")
        if darling_div and darling_div.has_attr("x-data"):
            match = re.search(r"darlingTitle:\s*`(.*?)`", darling_div["x-data"])
            if match:
                title = match.group(1)

    if author_el and author_el.get_text(strip=True):
        author = author_el.get_text(strip=True)

    if body_el:
        # Get all paragraphs from the body
        paragraphs = body_el.find_all('p')
        if paragraphs:
            body = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        else:
            body = body_el.get_text(strip=True)

    # Strategy 2: Fallback to broader search if specific selectors fail
    if not body:
        for section in soup.find_all(['div', 'section', 'article']):
            text = section.get_text()
            if '糸井重里' in text and len(text) > 500:
                paragraphs = section.find_all('p')
                if paragraphs:
                    body = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    h_tag = section.find(['h1', 'h2', 'h3'])
                    if h_tag and not title:
                        title = h_tag.get_text(strip=True)
                    break

    if not body or len(body) < 200:
        print("Could not extract essay content")
        return None

    # Clean up the essay text
    lines = body.split('\n')
    cleaned_lines = []
    seen_lines = set()
    for line in lines:
        # Skip footer lines about update times
        if 'ほぼ日の更新時間' in line:
            continue
        # Skip duplicate lines
        if line.strip() in seen_lines:
            continue
        seen_lines.add(line.strip())
        cleaned_lines.append(line)
    body = '\n'.join(cleaned_lines).strip()

    # Generate a hash to detect duplicate content
    content_hash = hashlib.md5(body.encode()).hexdigest()[:12]

    return {
        'title': title or f"今日のダーリン - {datetime.now().strftime('%Y年%m月%d日')}",
        'author': author or "糸井重里",
        'body': body,
        'date': datetime.now(timezone.utc).isoformat(),
        'hash': content_hash,
    }


def translate_text(japanese_text: str, is_title: bool = False) -> str:
    """Translate text using Claude API."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)

    if is_title:
        prompt = f"""Translate this Japanese essay title into natural English.
Output only the translated title, nothing else.

{japanese_text}"""
    else:
        prompt = f"""You are translating a Japanese personal essay into natural, literary English.
Do not translate word-for-word—your goal is to preserve the author's original voice, tone, and nuance for a native English reader.
Do not include boilerplate like 'Here is the translation.' Do not explain your output.
Preserve paragraph breaks (two line breaks = new paragraph).
Respect any formatting (e.g., unusual spacing, symbols like ・, etc.) where it contributes to tone.
If there is a phrase or idiom that doesn't translate easily, include a minimal footnote only if necessary.

{japanese_text}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def summarize_translation(translation: str) -> str:
    """Generate a 1-2 line summary from the translated essay."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)

    prompt = f"""Create a brief 1-2 sentence summary of this essay that captures its main theme or insight.
Be concise and natural. Output only the summary, nothing else.

{translation}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()


def load_archive() -> list:
    """Load existing archive of essays."""
    if ARCHIVE_FILE.exists():
        with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_archive(archive: list):
    """Save archive to disk."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)


def generate_rss(archive: list):
    """Generate RSS feed from archive."""
    fg = FeedGenerator()
    fg.id('https://adtheriault.github.io/itoi-daily/')
    fg.title("Itoi's Daily Essay (Translated)")
    fg.author({'name': 'Shigesato Itoi', 'email': 'translated@example.com'})
    fg.link(href='https://adtheriault.github.io/itoi-daily/', rel='alternate')
    fg.link(href='https://adtheriault.github.io/itoi-daily/feed.xml', rel='self')
    fg.subtitle('Daily essays by Shigesato Itoi from 1101.com, translated to English')
    fg.language('en')
    fg.image(url=DARLING_IMAGE_URL, title="Itoi's Daily Essay", link='https://www.1101.com/')

    # Add entries (most recent first, limit to 30)
    for entry_data in archive[:30]:
        fe = fg.add_entry()
        fe.id(f"https://adtheriault.github.io/itoi-daily/#{entry_data['hash']}")
        fe.title(entry_data.get('translated_title', entry_data['title']))
        fe.link(href='https://www.1101.com/')

        # Use summary for description (1-2 line summary)
        summary = entry_data.get('summary', '')
        fe.description(summary)

        # Add full translation as content:encoded
        translation = entry_data['translation']
        fe.content(content=translation, type='html')

        fe.published(entry_data['date'])
        fe.updated(entry_data['date'])

    OUTPUT_DIR.mkdir(exist_ok=True)
    fg.rss_file(str(FEED_FILE), pretty=True)

    # Post-process XML to add namespaces, dc:author, dc:publisher, and media:thumbnail
    with open(FEED_FILE, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # Add namespaces to the root rss element
    if 'xmlns:dc=' not in xml_content:
        xml_content = xml_content.replace(
            '<rss',
            '<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/"',
            1
        )

    # Add dc:publisher after the language tag if not present
    if '<dc:publisher>' not in xml_content:
        xml_content = xml_content.replace(
            '</language>',
            '</language>\n    <dc:publisher>Hobonichi</dc:publisher>'
        )

    # Add dc:author and media:thumbnail to each item
    import re
    for entry_data in archive[:30]:
        author = entry_data.get('translated_author', entry_data.get('author', 'Shigesato Itoi'))
        author_tag = f'<dc:author>{author}</dc:author>'
        thumbnail_tag = f'<media:thumbnail url="{DARLING_IMAGE_URL}" width="200" height="200"/>'

        # Find the item for this entry and add author/thumbnail after guid
        guid = entry_data['hash']
        pattern = f'<guid isPermaLink="false">https://adtheriault.github.io/itoi-daily/#{guid}</guid>'
        if pattern in xml_content:
            replacement = f'{pattern}\n    {author_tag}\n    {thumbnail_tag}'
            xml_content = xml_content.replace(pattern, replacement, 1)

    with open(FEED_FILE, 'w', encoding='utf-8') as f:
        f.write(xml_content)

    print(f"RSS feed written to {FEED_FILE}")


def main():
    print(f"Starting scrape at {datetime.now().isoformat()}")

    # Scrape today's essay
    essay = scrape_essay()
    if not essay:
        print("No essay found, exiting")
        return

    # Check if we already have this essay
    archive = load_archive()
    existing_hashes = {e['hash'] for e in archive}

    if essay['hash'] in existing_hashes:
        print(f"Essay already in archive (hash: {essay['hash']}), skipping")
        return

    # Translate title, author, and body
    print("Translating title...")
    translated_title = translate_text(essay['title'], is_title=True).strip()

    print("Translating author...")
    translated_author = translate_text(essay['author'], is_title=True).strip()

    print("Translating essay...")
    translation = translate_text(essay['body'])

    print("Generating summary...")
    summary = summarize_translation(translation)

    # Add to archive
    essay['translation'] = translation
    essay['summary'] = summary
    essay['translated_title'] = translated_title
    essay['translated_author'] = translated_author
    archive.insert(0, essay)  # Most recent first

    # Save and regenerate feed
    save_archive(archive)
    generate_rss(archive)

    print(f"Successfully processed: {essay['title']}")
    print(f"Translated title: {translated_title}")
    print(f"Summary: {summary}")


if __name__ == "__main__":
    main()
