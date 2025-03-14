# SEJU Stats Service

A service that monitors and extracts game data for registered players from coh3stats.com.

## Features

- Periodically checks for new games for registered players
- Separates custom games and auto matches into different collections
- Handles both JSON data extraction and table scraping
- Configurable check intervals and batch sizes
- Exports custom games to Google Sheets for ELO calculation
- Robust error handling and logging

## Configuration

The service uses environment variables for configuration. Create a `.env` file with the following variables:

```env
# MongoDB Configuration
MONGO_URI=your_mongodb_connection_string
CHECK_INTERVAL=900  # Time in seconds between checks (default: 15 minutes)
LOG_LEVEL=INFO     # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

# Google Sheets Configuration
GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
# Or provide the JSON directly:
# GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
GOOGLE_SHEETS_ID=1JHrIoReIXPsYJdfbcFdq1csHEH8HsoJkhin3wF5NkOs
GOOGLE_SHEETS_WORKSHEET=Auto Registro
```

## Directory Structure

```
sejusaas/
├── sejusaas/
│   ├── services/
│   │   ├── __init__.py
│   │   ├── game_monitor.py
│   │   └── sheets_exporter.py
│   ├── __init__.py
│   └── __main__.py
├── logs/
├── tests/
├── Dockerfile
├── requirements.txt
├── service-account.json
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
     -v $(pwd)/service-account.json:/app/service-account.json \
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

## Google Sheets Integration

The service can export custom games to a Google Sheet for ELO calculation. To set up the Google Sheets integration:

1. Create a Google Cloud project and enable the Google Sheets API
2. Create a service account with access to the Google Sheets API
3. Download the service account credentials as a JSON file
4. Save the credentials file as `service-account.json` in the project root
5. Share your Google Sheet with the service account email address (found in the credentials file)

### Google Sheets Configuration

The following environment variables can be used to configure the Google Sheets integration:

- `GOOGLE_SERVICE_ACCOUNT_FILE`: Path to the service account credentials file
- `GOOGLE_SERVICE_ACCOUNT_JSON`: Alternatively, provide the service account credentials as a JSON string
- `GOOGLE_SHEETS_ID`: ID of the Google Sheet to export to (default: `1JHrIoReIXPsYJdfbcFdq1csHEH8HsoJkhin3wF5NkOs`)
- `GOOGLE_SHEETS_WORKSHEET`: Name of the worksheet to export to (default: `Auto Registro`)

### Exported Data Format

The service exports custom games to the Google Sheet in the following format:

| Fecha | Hora | Mapa | Ejército Eje | Ejército Aliados | Jugador Eje 1-4 | Jugador Aliados 1-4 | Puntos Eje | Puntos Aliados | Match ID | Exportado |
|-------|------|------|--------------|------------------|-----------------|---------------------|------------|----------------|----------|-----------|
| Date  | Time | Map  | Axis         | Allies           | Player names    | Player names        | 500 or 0   | 500 or 0       | Unique ID| Timestamp |

The winning team receives 500 points, and the losing team receives 0 points.

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