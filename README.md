# SEJU Stats Service

A service that monitors and extracts game data for registered players from coh3stats.com.

## Features

- Periodically checks for new games for registered players
- Separates custom games and auto matches into different collections
- Handles both JSON data extraction and table scraping
- Configurable check intervals and batch sizes
- Robust error handling and logging

## Configuration

The service uses environment variables for configuration. Create a `.env` file with the following variables:

```env
MONGO_URI=your_mongodb_connection_string
CHECK_INTERVAL=900  # Time in seconds between checks (default: 15 minutes)
LOG_LEVEL=INFO     # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
```

## Directory Structure

```
sejusaas/
├── sejusaas/
│   ├── services/
│   │   ├── __init__.py
│   │   └── game_monitor.py
│   ├── __init__.py
│   └── __main__.py
├── logs/
├── tests/
├── Dockerfile
├── requirements.txt
└── README.md
```

## Running the Service

### Using Docker

1. Build the Docker image:
   ```bash
   docker build -t sejusaas .
   ```

2. Run the container:
   ```bash
   docker run -d \
     --name sejusaas \
     --env-file .env \
     sejusaas
   ```

### Without Docker

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

3. Run the service:
   ```bash
   python -m sejusaas
   ```

## MongoDB Collections

The service uses the following collections:

- `players`: Registered players to monitor
- `custom_games`: Custom games between registered players
- `automatches`: Auto matches with at least one registered player

### Collection Schemas

#### Players Collection
```json
{
  "player_id": "string",
  "player_name": "string",
  "added_at": "datetime"
}
```

#### Custom Games Collection
```json
{
  "match_id": "string",
  "unique_match_id": "string",
  "player_id": "string",
  "player_name": "string",
  "match_date": "string",
  "match_type": "string",
  "match_result": "string",
  "map_name": "string",
  "axis_players": [
    {
      "player_id": "string",
      "player_name": "string"
    }
  ],
  "allies_players": [
    {
      "player_id": "string",
      "player_name": "string"
    }
  ],
  "is_simulated": false,
  "is_scraped": true,
  "scraped_at": "datetime",
  "discovered_at": "datetime"
}
```

#### Auto Matches Collection
Same schema as Custom Games Collection.

## Logging

Logs are written to both stdout and `logs/sejusaas.log`. The log level can be configured using the `LOG_LEVEL` environment variable.

## Error Handling

The service includes robust error handling:
- Network errors: Retries with backoff
- Parsing errors: Logs errors and continues with next player
- MongoDB errors: Logs errors and retries after delay
- Browser errors: Restarts browser for each player

## Development

### Running Tests
```bash
pytest tests/
```

### Code Style
The code follows PEP 8 guidelines and uses type hints for better maintainability.
