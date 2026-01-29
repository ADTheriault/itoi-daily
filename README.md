# Itoi Daily

Daily translations of Shigesato Itoi's essays from [1101.com](https://www.1101.com/).

## Subscribe

Add this RSS feed to your reader:

```
https://adtheriault.github.io/itoi-daily/feed.xml
```

## About

Shigesato Itoi (糸井重里) is a Japanese copywriter, essayist, and creator of the *Mother* (EarthBound) video game series. He's written a daily essay called "今日のダーリン" (Today's Darling) on his website 1101.com (ほぼ日 / Hobonichi) for over 25 years.

This project automatically:
1. Scrapes Itoi's daily essay from 1101.com using Playwright (for JavaScript-rendered content)
2. Translates the title, author, and body to English using Claude API
3. Publishes it as an RSS feed with Itoi's signature image

## How It Works

- **Schedule:** Runs daily at 11:30 AM JST (2:30 AM UTC) via GitHub Actions, shortly after the site updates at 11 AM JST
- **Scraping:** Uses Playwright to render JavaScript content, then BeautifulSoup to extract from specific CSS selectors (`div.darling-title h2`, `div.darling-title h3`, `div.darling-text`)
- **Translation:** Uses Claude API (claude-sonnet-4) with a prompt designed to preserve Itoi's conversational, literary tone
- **Deduplication:** Content hashing prevents duplicate entries in the archive
- **Hosting:** RSS feed hosted on GitHub Pages

## Project Structure

```
├── scraper.py          # Main script: scrape, translate, generate RSS
├── requirements.txt    # Python dependencies (playwright, beautifulsoup4, anthropic, feedgen)
├── docs/
│   ├── feed.xml        # RSS feed (auto-generated)
│   └── archive.json    # Archive of translated essays (JSON)
└── .github/
    └── workflows/
        └── daily.yml   # GitHub Actions workflow
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium
playwright install-deps

# Set your API key
export ANTHROPIC_API_KEY="your-key"

# Run the scraper
python scraper.py
```

## Technical Notes

- The 1101.com site uses JavaScript to render content, which is why we use Playwright instead of simple HTTP requests
- Essays are identified by an MD5 hash of the body content to prevent re-translating the same essay
- The RSS feed includes Itoi's signature image and preserves paragraph formatting
- Archive is limited to the 30 most recent entries in the feed

## Acknowledgments

Inspired by [hellodarling](https://github.com/UpdogUpdogUpdog/hellodarling), a similar project.

## License

Translations are provided for personal/educational use. Original essays are copyright Shigesato Itoi / Hobonichi.
