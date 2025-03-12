# COH3 Stats Custom Games Tracker

A service that tracks custom games between registered players in Company of Heroes 3.

## Features

- Monitors registered players for new custom games
- Stores only games between registered players
- Prevents duplicate game storage
- Efficient batch processing to stay within free tier limits

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

## Adding Players

Use the MongoDB interface to add players to the `players` collection with the format:
```json
{
    "player_id": "123",
    "player_name": "player-name"
}
```
