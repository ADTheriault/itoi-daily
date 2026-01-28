# Itoi Daily

Daily translations of Shigesato Itoi's essays from [1101.com](https://www.1101.com/).

## Subscribe

Add this RSS feed to your reader:

```
https://adtheriault.github.io/itoi-daily/feed.xml
```

## About

Shigesato Itoi (糸井重里) is a Japanese copywriter, essayist, and creator of the *Mother* (EarthBound) video game series. He's written a daily essay on his website 1101.com (ほぼ日 / Hobonichi) for over 25 years.

This project automatically:
1. Scrapes Itoi's daily essay from 1101.com
2. Translates it to English using Claude AI
3. Publishes it as an RSS feed

## How It Works

- **Schedule:** Runs daily at 9:00 AM JST via GitHub Actions
- **Translation:** Uses Claude API (claude-sonnet) for natural translations that preserve Itoi's conversational tone
- **Hosting:** RSS feed hosted on GitHub Pages

## Project Structure

```
├── scraper.py          # Main script: scrape, translate, generate RSS
├── requirements.txt    # Python dependencies
├── docs/
│   ├── feed.xml        # RSS feed (auto-generated)
│   ├── archive.json    # Archive of translated essays
│   └── index.html      # Landing page
└── .github/
    └── workflows/
        └── daily.yml   # GitHub Actions workflow
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY="your-key"

# Run the scraper
python scraper.py
```

## License

Translations are provided for personal/educational use. Original essays are © Shigesato Itoi / Hobonichi.
