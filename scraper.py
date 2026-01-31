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
from typing import Optional

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
HOBONICHI_ICON_URL = "https://adtheriault.github.io/itoi-daily/hobonichi%20logo.png"


def scrape_essay() -> Optional[dict]:
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

    # Clean up the essay text while preserving paragraph breaks
    paragraphs = body.split('\n\n')
    cleaned_paragraphs = []
    seen_paragraphs = set()
    for para in paragraphs:
        # Clean within paragraph (handle any single newlines)
        para_lines = para.split('\n')
        cleaned_para_lines = []
        for line in para_lines:
            # Skip footer lines about update times
            if 'ほぼ日の更新時間' in line:
                continue
            cleaned_para_lines.append(line)
        para = '\n'.join(cleaned_para_lines).strip()

        if not para:
            continue
        # Skip duplicate paragraphs
        if para in seen_paragraphs:
            continue
        seen_paragraphs.add(para)
        cleaned_paragraphs.append(para)
    body = '\n\n'.join(cleaned_paragraphs).strip()

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
        # Count paragraphs to tell Claude exactly how many <p> tags to output
        paragraph_count = len([p for p in japanese_text.split('\n\n') if p.strip()])
        prompt = f"""You are translating a Japanese personal essay into natural, literary English.
Do not translate word-for-word—your goal is to preserve the author's original voice, tone, and nuance for a native English reader.
Do not include boilerplate like 'Here is the translation.' Do not explain your output.

CRITICAL: The input has {paragraph_count} paragraphs separated by blank lines. You MUST output exactly {paragraph_count} separate <p> tags.

Example - if the input is:
段落1です。

段落2です。

段落3です。

Then output MUST be:
<p>This is paragraph 1.</p>
<p>This is paragraph 2.</p>
<p>This is paragraph 3.</p>

Rules:
- Each blank-line-separated paragraph becomes ONE <p>...</p> tag
- Do NOT combine multiple paragraphs into one <p> tag
- Do NOT use markdown or plain text
- Output ONLY the <p> tags—no wrapper elements

IMPORTANT: Preserve proper names and brand names:
- "ほぼ日刊イトイ新聞" or "ほぼ日" should be rendered as "Hobonichi"

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


def generate_atom(archive: list):
    """Generate Atom feed from archive."""
    fg = FeedGenerator()
    fg.id('https://adtheriault.github.io/itoi-daily/feed.xml')
    fg.title("Today's Darling")
    fg.subtitle('Daily essays by Shigesato Itoi from 1101.com, translated to English.')
    fg.link(href='https://www.1101.com/', rel='alternate', type='text/html')
    fg.link(href='https://adtheriault.github.io/itoi-daily/feed.xml', rel='self', type='application/atom+xml')
    fg.language('en')
    fg.icon(HOBONICHI_ICON_URL)

    # Add entries (most recent first, limit to 30)
    for entry_data in archive[:30]:
        fe = fg.add_entry()
        fe.id(f"https://adtheriault.github.io/itoi-daily/#{entry_data['hash']}")
        fe.title(entry_data.get('translated_title', entry_data['title']))
        fe.author({'name': entry_data.get('translated_author', entry_data.get('author', 'Shigesato Itoi'))})
        fe.link(href='https://www.1101.com/', rel='alternate', type='text/html')

        # Use summary for description (1-2 line summary)
        summary = entry_data.get('summary', '')
        fe.summary(summary)

        # Add full translation as content with centered header image
        translation = entry_data['translation']
        # Prepend a centered image at the top of the content
        image_html = f'<div style="text-align: center; margin-bottom: 20px;"><img src="{DARLING_IMAGE_URL}" alt="Hobonichi Darling" style="max-width: 300px; height: auto;"/></div>'
        content_with_image = image_html + translation
        fe.content(content=content_with_image, type='html')

        fe.published(entry_data['date'])
        fe.updated(entry_data['date'])

    OUTPUT_DIR.mkdir(exist_ok=True)
    fg.atom_file(str(FEED_FILE), pretty=True)

    # Post-process to match the desired header format
    with open(FEED_FILE, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # Add thr and media namespaces if not present
    if 'xmlns:media=' not in xml_content:
        xml_content = xml_content.replace(
            '<feed xmlns="http://www.w3.org/2005/Atom"',
            '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" xmlns:thr="http://purl.org/syndication/thread/1.0"',
            1
        )
    elif 'xmlns:thr=' not in xml_content:
        xml_content = xml_content.replace(
            '<feed xmlns="http://www.w3.org/2005/Atom"',
            '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:thr="http://purl.org/syndication/thread/1.0"',
            1
        )

    # Add type="text" to title element
    if '<title type=' not in xml_content:
        xml_content = xml_content.replace(
            '<title>',
            '<title type="text">',
            1
        )

    # Reorder feed header elements to match convention:
    # title, subtitle, updated, link(alternate), id, link(self), icon
    import re
    feed_match = re.search(r'<feed[^>]*>.*?(?=<entry|</feed>)', xml_content, re.DOTALL)
    if feed_match:
        feed_section = feed_match.group(0)

        # Extract individual elements
        title_match = re.search(r'(<title[^>]*>.*?</title>)', feed_section)
        subtitle_match = re.search(r'(<subtitle>.*?</subtitle>)', feed_section)
        updated_match = re.search(r'(<updated>.*?</updated>)', feed_section)
        links = re.findall(r'(<link[^>]*/?>)', feed_section)
        id_match = re.search(r'(<id>.*?</id>)', feed_section)
        icon_match = re.search(r'(<icon>.*?</icon>)', feed_section)
        generator_match = re.search(r'(<generator[^>]*>.*?</generator>)', feed_section)

        # Reconstruct in desired order with all namespaces
        new_feed = '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" xmlns:thr="http://purl.org/syndication/thread/1.0" xml:lang="en">\n'
        if title_match:
            new_feed += '  ' + title_match.group(1) + '\n'
        if subtitle_match:
            new_feed += '  ' + subtitle_match.group(1) + '\n'
        if updated_match:
            new_feed += '  ' + updated_match.group(1) + '\n'
        # Add links in order: alternate first, then self
        for link in links:
            if 'rel="alternate"' in link:
                new_feed += '  ' + link + '\n'
        if id_match:
            new_feed += '  ' + id_match.group(1) + '\n'
        for link in links:
            if 'rel="self"' in link:
                new_feed += '  ' + link + '\n'
        if icon_match:
            new_feed += '  ' + icon_match.group(1) + '\n'

        # Replace the feed opening with our reconstructed one
        xml_content = new_feed + xml_content[feed_match.end():]

    # Add media:thumbnail to each entry
    for entry_data in archive[:30]:
        guid = entry_data['hash']
        entry_id_pattern = f'<id>https://adtheriault.github.io/itoi-daily/#{guid}</id>'
        if entry_id_pattern in xml_content:
            # Add thumbnail after the published element
            thumbnail_tag = f'<media:thumbnail url="{DARLING_IMAGE_URL}" width="200" height="200"/>'
            published_pattern = '</published>'
            # Find the published tag that comes after this entry's id
            entry_start = xml_content.find(entry_id_pattern)
            if entry_start != -1:
                # Find the next </published> after this entry
                published_end = xml_content.find(published_pattern, entry_start)
                if published_end != -1:
                    insertion_point = published_end + len(published_pattern)
                    # Check if thumbnail already exists for this entry
                    check_range = xml_content[entry_start:entry_start + 1500]
                    if f'<media:thumbnail' not in check_range:
                        xml_content = xml_content[:insertion_point] + '\n  ' + thumbnail_tag + xml_content[insertion_point:]

    # Write final XML
    with open(FEED_FILE, 'w', encoding='utf-8') as f:
        f.write(xml_content)


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
    generate_atom(archive)

    print(f"Successfully processed: {essay['title']}")
    print(f"Translated title: {translated_title}")
    print(f"Summary: {summary}")


if __name__ == "__main__":
    main()
