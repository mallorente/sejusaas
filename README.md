# COH3 Stats Custom Games Tracker

A service that tracks custom games between registered players in Company of Heroes 3.

## Features

- Monitors registered players for new custom games
- Tracks automatch games with registered players
- Stores custom games between registered players in a dedicated collection
- Stores automatch games with registered players in a separate collection
- Prevents duplicate game storage
- Efficient batch processing to stay within free tier limits
- Comprehensive logging system with configurable log levels
- Runtime log level adjustment without restart
- Persistent log storage in files

## Deployment on Render

1. Fork/Clone this repository to your GitHub account

2. Create a new Render account at https://render.com if you don't have one

3. In Render Dashboard:
   - Click "New +"
   - Select "Blueprint"
   - Connect your GitHub repository
   - Select the repository

4. Configure Environment Variables:
   - `MONGO_URI`: Your MongoDB connection string
   - `PYTHON_VERSION`: 3.11.8 (already set in render.yaml)

5. Deploy:
   - Render will automatically detect the `render.yaml` configuration
   - Click "Apply" to start the deployment

## Deployment with Docker

1. Ensure Docker and Docker Compose are installed on your system:
   - [Docker Installation Guide](https://docs.docker.com/get-docker/)
   - [Docker Compose Installation Guide](https://docs.docker.com/compose/install/)

2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/coh3stats.git
   cd coh3stats
   ```

3. Create required directories:
   ```bash
   mkdir -p logs samples/html samples/json
   ```

4. Create a `.env` file with your MongoDB URI:
   ```
   MONGO_URI=mongodb+srv://your_username:your_password@your_cluster.mongodb.net/
   ```

5. Build and start the Docker container:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

6. Check the logs:
   ```bash
   docker logs coh3stats-worker
   ```

7. Monitor and manage:
   - Stop the service: `docker-compose down`
   - Restart the service: `docker-compose restart`
   - View logs in real-time: `docker logs -f coh3stats-worker`
   - Change log level: `docker exec coh3stats-worker python change_log_level.py [debug|info|warning|error|critical]`

8. Container health checks:
   - The container includes a health check that runs every hour
   - You can check the health status with: `docker inspect --format='{{.State.Health.Status}}' coh3stats-worker`

### Directory Structure

The Docker deployment uses the following directory structure:
```
sejusaas/
├── logs/           # Contains application logs
└── samples/        # Contains scraped data
    ├── html/       # HTML samples
    └── json/       # JSON samples
```

These directories are mounted as volumes in the container to persist data between restarts.

## Local Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your MongoDB URI:
   ```
   MONGO_URI=your_mongodb_connection_string
   ```

4. Run tests:
   ```bash
   python -m pytest tests/
   ```

5. Run the service:
   ```bash
   python main.py
   ```

## Monitoring

The service will:
- Check for new games every 15 minutes
- Process players in batches of 5
- Log all activities to the console
- Stay within Render's free tier limits (500 minutes/month)

## Logging System

The application includes a comprehensive logging system with the following features:

### Log Levels

- **DEBUG**: Detailed information for troubleshooting
- **INFO**: General operational information (default)
- **WARNING**: Potential issues that don't prevent execution
- **ERROR**: Errors that affect specific operations
- **CRITICAL**: Critical errors that may stop the application

### Changing Log Levels

You can change the log level in three ways:

1. **Using signals** (runtime):
   - On Linux/Unix: `kill -SIGUSR1 <PID>`
   - On Windows: Press `Ctrl+Break`
   - This rotates through: INFO → DEBUG → WARNING → INFO

2. **Using the database** (runtime):
   - Run the script: `python change_log_level.py [debug|info|warning|error|critical]`
   - If no level is specified, it cycles through the levels

3. **Using environment variables** (startup):
   - Set `LOG_LEVEL=DEBUG` in your `.env` file or environment
   - In Docker: modify the `LOG_LEVEL` in `docker-compose.yml`
   - In Render: update the environment variable in the dashboard

### Log Storage

- **Console**: All logs are displayed in the console
- **File**: Logs are also saved to `logs/coh3stats.log`
  - In Docker, these are persisted in the mounted volume
  - In Render, these are stored in the ephemeral filesystem

### Log Format

Each log entry includes:
- Timestamp
- Logger name
- Log level
- Message

## Adding Players

Use the MongoDB interface to add players to the `players` collection with the format:
```json
{
    "player_id": "123",
    "player_name": "player-name"
}
```
