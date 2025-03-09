# COH3 Stats Analyzer

This project provides tools to analyze player data and match history from Company of Heroes 3.

## Features

- Fetch player data from coh3stats.com
- Extract match data using HTML scraping
- Fetch match data using the API
- Analyze match history and identify custom games
- Store data in MongoDB

## Directory Structure

- `main.py`: Main application file
- `fetch_real_matches.py`: API method for fetching match data
- `extract_from_html.py`: HTML extraction utilities
- `scrape_with_playwright.py`: Playwright-based scraping
- `tests/`: Test directory
- `samples/`: Sample data directory

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Configure MongoDB connection in `.env`
3. Run the application: `python main.py`

## Methods

### HTML Scraping

The application can extract match data from the HTML of a player's page on coh3stats.com. This method is more reliable than the API method, as it extracts data directly from the website.

### API Method

The application can also fetch match data using the coh3stats.com API. This method is used as a fallback if HTML scraping fails.
