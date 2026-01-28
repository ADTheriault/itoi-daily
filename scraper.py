#!/usr/bin/env python3
"""
Itoi Daily Essay Scraper & Translator

Scrapes Shigesato Itoi's daily essay from 1101.com,
translates it via Claude API, and updates an RSS feed.
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic
from feedgen.feed import FeedGenerator


# Configuration
ESSAY_URL = "https://www.1101.com/"
OUTPUT_DIR = Path(__file__).parent / "docs"
FEED_FILE = OUTPUT_DIR / "feed.xml"
ARCHIVE_FILE = OUTPUT_DIR / "archive.json"


def scrape_essay() -> dict | None:
    """Fetch and extract Itoi's daily essay from 1101.com."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "ja,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = requests.get(ESSAY_URL, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
    except requests.RequestException as e:
        print(f"Failed to fetch page: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract essay content - multiple selector strategies
    essay_text = None
    title = None

    # Strategy 1: Look for Itoi's column section by author name
    for section in soup.find_all(['div', 'section', 'article']):
        text = section.get_text()
        if '糸井重里' in text and len(text) > 500:
            # Found a substantial section mentioning Itoi
            paragraphs = section.find_all('p')
            if paragraphs:
                essay_text = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                # Try to find title
                h_tag = section.find(['h1', 'h2', 'h3'])
                if h_tag:
                    title = h_tag.get_text(strip=True)
                break

    # Strategy 2: Broader search if strategy 1 fails
    if not essay_text:
        # Look for main content area
        main = soup.find('main') or soup.find('div', {'id': 'main'}) or soup.find('div', {'class': 'main'})
        if main:
            paragraphs = main.find_all('p')
            japanese_paragraphs = [p.get_text(strip=True) for p in paragraphs
                                   if p.get_text(strip=True) and any('\u3040' <= c <= '\u30ff' for c in p.get_text())]
            if japanese_paragraphs:
                essay_text = '\n\n'.join(japanese_paragraphs[:20])  # Limit to first 20 paragraphs

    if not essay_text or len(essay_text) < 200:
        print("Could not extract essay content")
        return None

    # Clean up the essay text - remove footer lines about update times
    lines = essay_text.split('\n')
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
    essay_text = '\n'.join(cleaned_lines).strip()

    # Generate a hash to detect duplicate content
    content_hash = hashlib.md5(essay_text.encode()).hexdigest()[:12]

    return {
        'title': title or f"今日のダーリン - {datetime.now().strftime('%Y年%m月%d日')}",
        'body': essay_text,
        'date': datetime.now(timezone.utc).isoformat(),
        'hash': content_hash,
    }


def translate_essay(japanese_text: str, title: str) -> str:
    """Translate essay using Claude API."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""Translate this Japanese essay by Shigesato Itoi into natural, readable English.

Guidelines:
- Preserve Itoi's warm, conversational, and reflective tone
- Keep the translation flowing naturally - don't be overly literal
- For cultural references that English readers might not know, add a brief [translator's note] inline
- Preserve any wordplay or puns where possible, with explanation if needed
- Keep paragraph breaks as in the original

Title: {title}

Essay:
{japanese_text}"""
        }]
    )

    return message.content[0].text


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

    # Add entries (most recent first, limit to 30)
    for entry_data in archive[:30]:
        fe = fg.add_entry()
        fe.id(f"https://adtheriault.github.io/itoi-daily/#{entry_data['hash']}")
        fe.title(entry_data.get('translated_title', entry_data['title']))
        fe.link(href='https://www.1101.com/')
        fe.description(entry_data['translation'])
        fe.published(entry_data['date'])
        fe.updated(entry_data['date'])

    OUTPUT_DIR.mkdir(exist_ok=True)
    fg.rss_file(str(FEED_FILE), pretty=True)
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

    # Translate
    print("Translating essay...")
    translation = translate_essay(essay['body'], essay['title'])

    # Extract translated title (first line if it looks like a title)
    lines = translation.strip().split('\n')
    translated_title = lines[0] if lines and len(lines[0]) < 100 else essay['title']

    # Add to archive
    essay['translation'] = translation
    essay['translated_title'] = translated_title
    archive.insert(0, essay)  # Most recent first

    # Save and regenerate feed
    save_archive(archive)
    generate_rss(archive)

    print(f"Successfully processed: {essay['title']}")
    print(f"Translated title: {translated_title}")


if __name__ == "__main__":
    main()
