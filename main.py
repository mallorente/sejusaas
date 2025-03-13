import requests
from bs4 import BeautifulSoup
import pymongo
from datetime import datetime, timedelta
import time
import os
import re
import json
import random
import logging
import signal
from dotenv import load_dotenv
import hashlib
from playwright.sync_api import sync_playwright

# Configure logging
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# Default log level
current_log_level = os.getenv('LOG_LEVEL', 'INFO')

# Setup logger
logger = logging.getLogger('coh3stats')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(LOG_LEVELS.get(current_log_level, logging.INFO))

# Add file handler if logs directory exists
logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.exists(logs_dir):
    try:
        os.makedirs(logs_dir)
    except Exception as e:
        logger.warning(f"Could not create logs directory: {e}")

try:
    file_handler = logging.FileHandler(os.path.join(logs_dir, 'coh3stats.log'))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info("Log file handler added")
except Exception as e:
    logger.warning(f"Could not set up file logging: {e}")

# Function to change log level on the fly
def change_log_level(signum, frame):
    global current_log_level
    # Rotate through log levels: INFO -> DEBUG -> WARNING -> INFO
    if current_log_level == 'INFO':
        current_log_level = 'DEBUG'
    elif current_log_level == 'DEBUG':
        current_log_level = 'WARNING'
    else:
        current_log_level = 'INFO'
    
    new_level = LOG_LEVELS.get(current_log_level, logging.INFO)
    logger.setLevel(new_level)
    logger.info(f"Log level changed to: {current_log_level}")

# Register signal handler for SIGUSR1 (on Linux/Unix) or SIGBREAK (on Windows)
if os.name == 'posix':
    signal.signal(signal.SIGUSR1, change_log_level)
    logger.info("Send SIGUSR1 signal to change log level (kill -SIGUSR1 PID)")
else:
    try:
        signal.signal(signal.SIGBREAK, change_log_level)
        logger.info("Press Ctrl+Break to change log level")
    except AttributeError:
        logger.warning("Log level change via signal not supported on this platform")

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://usuario:contraseña@cluster0.mongodb.net/")
DB_NAME = "coh3stats_db"
PLAYERS_COLLECTION = "players"
MATCHES_COLLECTION = "matches"
CUSTOM_GAMES_COLLECTION = "custom_games"
AUTO_MATCHES_COLLECTION = "automatches"  # Nueva colección para partidas automáticas
CONFIG_COLLECTION = "config"  # Collection for configuration

# Constants for optimization
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 15 * 60))  # Default to 15 minutes if not set
BATCH_SIZE = 5  # Number of players to check in each batch
ERROR_WAIT_TIME = 60  # 1 minute wait on error
LOG_CHECK_INTERVAL = 60  # Check for log level changes every 60 seconds

# Available maps in the game
AVAILABLE_MAPS = [
    "Fields of Normandy",
    "Montherme",
    "Montecassino",
    "Souville",
    "Rails and Sand",
    "Rural Town",
    "Eindhoven",
    "Elst Outskirts",
    "Rural Castle",
    "Torrente",
    "Primosole",
    "Santuario",
    "Crossing in the Woods",
    "Desert Airfield",
    "Mountain Ruins",
    "Longstop Hill",
    "Benghazi",
    "Industrial Railyard",
    "Gothic Line",
    "Monte Cavo"
]

class COH3StatsAnalyzer:
    def __init__(self):
        logger.info("Initializing COH3StatsAnalyzer")
        # Connect to MongoDB
        try:
            self.client = pymongo.MongoClient(MONGO_URI)
            self.db = self.client[DB_NAME]
            self.players_collection = self.db[PLAYERS_COLLECTION]
            self.matches_collection = self.db[MATCHES_COLLECTION]
            self.custom_games_collection = self.db[CUSTOM_GAMES_COLLECTION]
            self.auto_matches_collection = self.db[AUTO_MATCHES_COLLECTION]
            self.config_collection = self.db[CONFIG_COLLECTION]
            logger.info(f"Connected to MongoDB database: {DB_NAME}")
        except Exception as e:
            logger.critical(f"Failed to connect to MongoDB: {str(e)}")
            raise
        
        # Track last check time for each player
        self.last_check_times = {}
        
        # Track last log level check time
        self.last_log_check = datetime.now()
        
        logger.debug("Initialization complete")
    
    def check_log_level(self):
        """Check if log level has been changed in the database"""
        global current_log_level
        
        now = datetime.now()
        # Only check periodically to avoid too many DB queries
        if (now - self.last_log_check).total_seconds() < LOG_CHECK_INTERVAL:
            return
        
        self.last_log_check = now
        
        try:
            config = self.config_collection.find_one({"key": "log_level"})
            if config and config["value"] != current_log_level:
                new_level = config["value"]
                if new_level in LOG_LEVELS:
                    logger.info(f"Changing log level from {current_log_level} to {new_level} (from database)")
                    current_log_level = new_level
                    logger.setLevel(LOG_LEVELS[new_level])
        except Exception as e:
            logger.warning(f"Error checking log level from database: {e}")
        
    def get_players_to_analyze(self):
        """Get the list of players to analyze from the database"""
        logger.debug("Getting players to analyze")
        current_time = datetime.now()
        
        # Get all players and sort by last check time
        players = list(self.players_collection.find({}))
        logger.info(f"Found {len(players)} players in database")
        
        # Update check times for new players
        for player in players:
            player_id = player['player_id']
            if player_id not in self.last_check_times:
                self.last_check_times[player_id] = current_time - timedelta(hours=1)
                logger.debug(f"Initialized check time for player {player['player_name']} (ID: {player_id})")
        
        # Sort players by last check time (oldest first)
        players.sort(key=lambda p: self.last_check_times.get(p['player_id'], datetime.min))
        
        batch = players[:BATCH_SIZE]
        logger.info(f"Selected batch of {len(batch)} players to analyze")
        logger.debug(f"Batch players: {', '.join([p['player_name'] for p in batch])}")
        return batch
    
    def add_player(self, player_id, player_name):
        """Add a new player to the database"""
        logger.info(f"Adding player {player_name} (ID: {player_id})")
        player_data = {
            "player_id": player_id,
            "player_name": player_name,
            "added_at": datetime.now()
        }
        self.players_collection.update_one(
            {"player_id": player_id},
            {"$set": player_data},
            upsert=True
        )
        logger.info(f"Player {player_name} (ID: {player_id}) added successfully")
    
    def extract_player_data(self, html_content):
        """Extract player data from the HTML of the page"""
        try:
            # Find the script that contains the player data
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_content, re.DOTALL)
            if not match:
                return None
                
            json_data = json.loads(match.group(1))
            
            # Extract relevant data
            player_data = json_data.get('props', {}).get('pageProps', {}).get('playerDataAPI', {})
            
            return player_data
        except Exception as e:
            print(f"Error extracting player data: {str(e)}")
            return None
    
    def scrape_player_data(self, player_id, player_name):
        """Get complete data for a player"""
        url = f"https://coh3stats.com/players/{player_id}/{player_name}"
        
        try:
            # Make HTTP request
            response = requests.get(url)
            response.raise_for_status()
            
            # Extract player data
            player_data = self.extract_player_data(response.text)
            
            if not player_data:
                print(f"Could not extract data for {player_name}")
                return None
                
            return player_data
                
        except Exception as e:
            print(f"Error getting data for {player_name}: {str(e)}")
            return None
    
    def get_real_matches_from_html(self, player_id, player_name):
        """
        Get real match data by extracting it from the HTML table on the player's page using Playwright
        """
        logger.info(f"Getting real match data for player: {player_name} (ID: {player_id})")
        
        try:
            with sync_playwright() as p:
                # Launch browser
                browser = p.chromium.launch()
                page = browser.new_page()
                
                # Go to player's page
                url = f"https://coh3stats.com/players/{player_id}/{player_name}"
                logger.debug(f"Navigating to URL: {url}")
                page.goto(url)
                
                # Wait for the matches table to load
                page.wait_for_selector('table[class*="matches-table"]')
                
                # Get the HTML content
                html_content = page.content()
                
                # Close browser
                browser.close()
                
                # Extract match data from the HTML
                matches = self.extract_match_data_from_table(html_content, player_id, player_name)
                
                logger.info(f"Found {len(matches)} matches for player {player_name}")
                return matches
            
        except Exception as e:
            logger.error(f"Error getting data for {player_name}: {str(e)}")
            return []
    
    def extract_match_data_from_table(self, html_content, player_id, player_name):
        """
        Extract match data from the HTML table in the player page
        """
        logger.debug(f"Extracting match data for player {player_name}")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the match table - buscar por la clase específica de la tabla de partidas recientes
        match_table = soup.find('table', {'class': lambda x: x and 'matches-table' in x})
        if not match_table:
            logger.warning("No match table found in the HTML")
            return []
        
        # Get all rows except the header
        rows = match_table.find_all('tr')[1:]  # Skip header row
        
        matches = []
        for row in rows:
            try:
                # Extract cells
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue
                
                # Extract match date
                date_cell = cells[0]
                date_text = date_cell.find('time')['datetime'] if date_cell.find('time') else date_cell.get_text(strip=True)
                
                # Extract match result and rating change
                result_cell = cells[1]
                result_div = result_cell.find('div', {'class': lambda x: x and 'row-indicator' in x})
                match_result = "Victory" if result_div and 'win-indicator' in result_div.get('class', []) else "Defeat"
                
                rating_change = None
                rating_span = result_cell.find('span', {'class': lambda x: x and ('positive' in x or 'negative' in x)})
                if rating_span:
                    rating_change = rating_span.get_text(strip=True)
                
                # Extract map
                map_cell = cells[4]
                map_name = map_cell.get_text(strip=True)
                
                # Extract game mode and duration
                mode_cell = cells[5]
                mode_text = mode_cell.get_text(strip=True)
                mode_parts = mode_text.split('•') if '•' in mode_text else [mode_text, '']
                mode = mode_parts[0].strip()
                duration = mode_parts[1].strip() if len(mode_parts) > 1 else ''
                
                # Extract axis players
                axis_cell = cells[2]
                axis_players = []
                for player_link in axis_cell.find_all('a'):
                    player_href = player_link.get('href', '')
                    player_id_match = re.search(r'/players/(\d+)', player_href)
                    if player_id_match:
                        player_id_from_link = player_id_match.group(1)
                        player_name_from_link = player_link.get_text(strip=True)
                        axis_players.append({
                            'player_id': player_id_from_link,
                            'player_name': player_name_from_link
                        })
                
                # Extract allies players
                allies_cell = cells[3]
                allies_players = []
                for player_link in allies_cell.find_all('a'):
                    player_href = player_link.get('href', '')
                    player_id_match = re.search(r'/players/(\d+)', player_href)
                    if player_id_match:
                        player_id_from_link = player_id_match.group(1)
                        player_name_from_link = player_link.get_text(strip=True)
                        allies_players.append({
                            'player_id': player_id_from_link,
                            'player_name': player_name_from_link
                        })
                
                # Generate a unique match ID basado en la fecha y los jugadores
                match_id_parts = [
                    date_text,
                    *[p['player_id'] for p in axis_players],
                    *[p['player_id'] for p in allies_players]
                ]
                match_id = hashlib.md5('_'.join(match_id_parts).encode()).hexdigest()
                
                # Create match object
                match = {
                    'match_id': match_id,
                    'player_id': player_id,
                    'player_name': player_name,
                    'match_date': date_text,
                    'match_type': mode,
                    'match_result': match_result,
                    'rating_change': rating_change,
                    'map_name': map_name,
                    'duration': duration,
                    'axis_players': axis_players,
                    'allies_players': allies_players,
                    'is_simulated': False,
                    'is_scraped': True,
                    'scraped_at': datetime.now().isoformat()
                }
                
                matches.append(match)
                logger.debug(f"Processed match {match_id} ({mode} on {map_name})")
                
            except Exception as e:
                logger.error(f"Error processing match row: {str(e)}")
                continue
        
        logger.info(f"Found {len(matches)} matches for {player_name}")
        return matches
    
    def get_real_matches(self, player_id, player_name, days_back=7):
        """
        Get real match data for a player directly from coh3stats.com
        """
        logger.info(f"Getting matches for player {player_name} (days back: {days_back})")
        return self.get_real_matches_from_html(player_id, player_name)
    
    def analyze_all_players(self):
        """Analyze recent matches for all players in the database"""
        players = self.get_players_to_analyze()
        
        if not players:
            print("No players in the database to analyze")
            return
        
        for player in players:
            player_id = player["player_id"]
            player_name = player["player_name"]
            
            print(f"Analyzing player: {player_name}")
            player_data = self.scrape_player_data(player_id, player_name)
            
            if player_data:
                print(f"Data obtained for {player_name}")
                
                # Update player information in the database
                self.players_collection.update_one(
                    {"player_id": player_id},
                    {"$set": {
                        "last_analyzed": datetime.now(),
                        "player_data": player_data
                    }}
                )
                
                # Get real matches
                matches = self.get_real_matches(player_id, player_name, 7)
                
                # Save matches to the database
                for match in matches:
                    # Check if the match already exists
                    if not self.matches_collection.find_one({"match_id": match["match_id"]}):
                        self.matches_collection.insert_one(match)
                        print(f"New match saved for {player_name}: {match['match_id']}")
            
            # Wait a bit between requests to avoid overloading the server
            time.sleep(2)
    
    def get_custom_games(self):
        """Get all saved custom games"""
        logger.debug("Retrieving custom games from database")
        games = list(self.custom_games_collection.find().sort("discovered_at", pymongo.DESCENDING))
        logger.debug(f"Retrieved {len(games)} custom games")
        return games

    def get_player_matches(self, player_id, player_name):
        """Get matches for a specific player"""
        logger.debug(f"Getting matches for player {player_name} (ID: {player_id})")
        try:
            # Calculate how long since last check
            last_check = self.last_check_times.get(player_id, datetime.min)
            hours_since_check = (datetime.now() - last_check).total_seconds() / 3600
            
            # Only check last hour if checked recently, otherwise check last day
            days_back = 1 if hours_since_check > 12 else 0.0417  # 0.0417 days = 1 hour
            logger.debug(f"Checking {days_back} days back for player {player_name}")
            
            matches = self.get_real_matches_from_html(player_id, player_name)
            
            # Update last check time
            self.last_check_times[player_id] = datetime.now()
            
            logger.info(f"Found {len(matches)} matches for player {player_name}")
            logger.debug(f"Match IDs: {[m.get('match_id', 'unknown') for m in matches]}")
            return matches
        except Exception as e:
            logger.error(f"Error getting matches for {player_name}: {str(e)}")
            return []
    
    def is_custom_game_between_players(self, match, registered_players):
        """Check if a match is a custom game between registered players"""
        match_id = match.get('match_id', 'unknown')
        logger.debug(f"Checking if match {match_id} is a custom game between registered players")
        
        # Get all player IDs from the match
        match_players = []
        for player in match.get('axis_players', []) + match.get('allies_players', []):
            match_players.append(player.get('player_id'))
        
        # Get all registered player IDs
        registered_player_ids = [p['player_id'] for p in registered_players]
        
        # Check if all players in the match are registered players
        all_players_registered = all(player_id in registered_player_ids for player_id in match_players)
        
        # Check if it's a custom game (match_type should contain "custom" or "Custom")
        is_custom = 'custom' in match.get('match_type', '').lower()
        
        result = is_custom and all_players_registered
        logger.debug(f"Match {match_id}: is_custom={is_custom}, all_players_registered={all_players_registered}, result={result}")
        return result
    
    def is_auto_match_with_registered_player(self, match, registered_players):
        """Check if a match is an auto match with at least one registered player"""
        match_id = match.get('match_id', 'unknown')
        logger.debug(f"Checking if match {match_id} is an auto match with registered player")
        
        # Get all player IDs from the match
        match_players = []
        for player in match.get('axis_players', []) + match.get('allies_players', []):
            match_players.append(player.get('player_id'))
        
        # Get all registered player IDs
        registered_player_ids = [p['player_id'] for p in registered_players]
        
        # Check if at least one player in the match is a registered player
        any_player_registered = any(player_id in registered_player_ids for player_id in match_players)
        
        # Check if it's NOT a custom game
        is_not_custom = 'custom' not in match.get('match_type', '').lower()
        
        result = is_not_custom and any_player_registered
        logger.debug(f"Match {match_id}: is_not_custom={is_not_custom}, any_player_registered={any_player_registered}, result={result}")
        return result
    
    def generate_unique_match_id(self, match):
        """Generate a unique match ID based on players and timestamp"""
        # Sort player IDs to ensure consistency
        player_ids = []
        for player in match.get('axis_players', []) + match.get('allies_players', []):
            player_ids.append(player.get('player_id'))
        player_ids.sort()
        
        # Create a unique string combining player IDs and match date
        unique_string = f"{'-'.join(player_ids)}_{match.get('match_date', '')}"
        
        # Use a hash of this string as the match ID
        unique_id = hashlib.md5(unique_string.encode()).hexdigest()
        logger.debug(f"Generated unique ID {unique_id} for match {match.get('match_id', 'unknown')}")
        return unique_id
    
    def check_for_new_games(self):
        """Check for new games (both custom and auto matches)"""
        # Check if log level has been changed
        self.check_log_level()
        
        logger.info(f"Starting check for new games at {datetime.now()}")
        
        # Get batch of players to analyze
        players_batch = self.get_players_to_analyze()
        if not players_batch:
            logger.warning("No players registered in the database")
            return
        
        logger.info(f"Checking batch of {len(players_batch)} players")
        
        # Get all registered players for validation
        all_registered_players = list(self.players_collection.find({}))
        logger.debug(f"Total registered players: {len(all_registered_players)}")
        
        new_custom_games_count = 0
        new_auto_matches_count = 0
        
        # Check each player in the batch
        for player in players_batch:
            player_id = player["player_id"]
            player_name = player["player_name"]
            
            logger.info(f"Checking matches for {player_name} (ID: {player_id})")
            matches = self.get_player_matches(player_id, player_name)
            
            for match in matches:
                match_id = match.get('match_id', 'unknown')
                match_type = match.get('match_type', 'unknown')
                match_date = match.get('match_date', 'unknown')
                
                logger.debug(f"Processing match {match_id} ({match_type}) from {match_date}")
                
                # Generate a unique ID for this match
                unique_match_id = self.generate_unique_match_id(match)
                match['unique_match_id'] = unique_match_id
                
                # Check if it's a custom game between registered players
                if self.is_custom_game_between_players(match, all_registered_players):
                    # Check if this match is already in the database
                    existing_match = self.custom_games_collection.find_one({"unique_match_id": unique_match_id})
                    if not existing_match:
                        logger.info(f"Found new custom game: {match_id} ({match_type}) from {match_date}")
                        match['discovered_at'] = datetime.now()
                        self.custom_games_collection.insert_one(match)
                        new_custom_games_count += 1
                        
                        # Log detailed match information
                        axis_players = [f"{p.get('player_name', 'unknown')} ({p.get('player_id', 'unknown')})" 
                                       for p in match.get('axis_players', [])]
                        allies_players = [f"{p.get('player_name', 'unknown')} ({p.get('player_id', 'unknown')})" 
                                         for p in match.get('allies_players', [])]
                        
                        logger.debug(f"Custom game details - Map: {match.get('map_name', 'unknown')}, "
                                    f"Result: {match.get('match_result', 'unknown')}, "
                                    f"Axis: {', '.join(axis_players)}, "
                                    f"Allies: {', '.join(allies_players)}")
                    else:
                        logger.debug(f"Custom game {match_id} already exists in database")
                
                # Check if it's an auto match with at least one registered player
                elif self.is_auto_match_with_registered_player(match, all_registered_players):
                    # Check if this match is already in the database
                    existing_match = self.auto_matches_collection.find_one({"unique_match_id": unique_match_id})
                    if not existing_match:
                        logger.info(f"Found new auto match: {match_id} ({match_type}) from {match_date}")
                        match['discovered_at'] = datetime.now()
                        self.auto_matches_collection.insert_one(match)
                        new_auto_matches_count += 1
                        
                        # Log detailed match information
                        axis_players = [f"{p.get('player_name', 'unknown')} ({p.get('player_id', 'unknown')})" 
                                       for p in match.get('axis_players', [])]
                        allies_players = [f"{p.get('player_name', 'unknown')} ({p.get('player_id', 'unknown')})" 
                                         for p in match.get('allies_players', [])]
                        
                        logger.debug(f"Auto match details - Map: {match.get('map_name', 'unknown')}, "
                                    f"Result: {match.get('match_result', 'unknown')}, "
                                    f"Axis: {', '.join(axis_players)}, "
                                    f"Allies: {', '.join(allies_players)}")
                    else:
                        logger.debug(f"Auto match {match_id} already exists in database")
                else:
                    logger.debug(f"Match {match_id} does not meet criteria for storage")
        
        logger.info(f"Found {new_custom_games_count} new custom games and {new_auto_matches_count} new auto matches in this batch")
    
    def get_auto_matches(self):
        """Get all saved auto matches"""
        logger.debug("Retrieving auto matches from database")
        matches = list(self.auto_matches_collection.find().sort("discovered_at", pymongo.DESCENDING))
        logger.debug(f"Retrieved {len(matches)} auto matches")
        return matches

def main():
    logger.info("Starting COH3 Stats Analyzer")
    logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
    logger.info(f"Batch size: {BATCH_SIZE} players")
    logger.info(f"Current log level: {current_log_level}")
    
    analyzer = COH3StatsAnalyzer()
    
    while True:
        try:
            # Check for new games
            start_time = time.time()
            analyzer.check_for_new_games()
            execution_time = time.time() - start_time
            
            # Calculate sleep time (ensure minimum 1 minute between checks)
            sleep_time = max(CHECK_INTERVAL - execution_time, 60)
            logger.info(f"Execution took {execution_time:.1f} seconds")
            logger.info(f"Waiting {sleep_time/60:.1f} minutes before next batch...")
            time.sleep(sleep_time)
            
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}", exc_info=True)
            logger.info(f"Waiting {ERROR_WAIT_TIME} seconds before retrying...")
            time.sleep(ERROR_WAIT_TIME)

if __name__ == "__main__":
    main() 