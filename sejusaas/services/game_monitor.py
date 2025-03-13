import os
import time
import json
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger('game_monitor')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://usuario:contraseña@cluster0.mongodb.net/")
DB_NAME = "coh3stats_db"
PLAYERS_COLLECTION = "players"
CUSTOM_GAMES_COLLECTION = "custom_games"
AUTO_MATCHES_COLLECTION = "automatches"

# Service configuration
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 15 * 60))  # Default to 15 minutes if not set
BATCH_SIZE = 5  # Number of players to check in each batch
ERROR_WAIT_TIME = 60  # 1 minute wait on error

class GameMonitorService:
    def __init__(self, mongo_client):
        """Initialize the game monitor service"""
        self.client = mongo_client
        self.db = self.client[DB_NAME]
        self.players_collection = self.db[PLAYERS_COLLECTION]
        self.custom_games_collection = self.db[CUSTOM_GAMES_COLLECTION]
        self.auto_matches_collection = self.db[AUTO_MATCHES_COLLECTION]
        self.last_check_times = {}
        logger.info("Game Monitor Service initialized")

    def get_players_to_analyze(self) -> List[Dict[str, Any]]:
        """Get a batch of players to analyze"""
        current_time = datetime.now()
        
        # Get all players and sort by last check time
        players = list(self.players_collection.find({}))
        logger.info(f"Found {len(players)} players in database")
        
        # Update check times for new players
        for player in players:
            player_id = player['player_id']
            if player_id not in self.last_check_times:
                self.last_check_times[player_id] = current_time
        
        # Sort players by last check time (oldest first)
        players.sort(key=lambda p: self.last_check_times.get(p['player_id'], datetime.min))
        
        batch = players[:BATCH_SIZE]
        logger.info(f"Selected batch of {len(batch)} players to analyze")
        return batch

    def generate_unique_match_id(self, match: Dict[str, Any]) -> str:
        """Generate a unique match ID based on players and timestamp"""
        # Sort player IDs to ensure consistency
        player_ids = []
        for player in match.get('axis_players', []) + match.get('allies_players', []):
            player_ids.append(player.get('player_id'))
        player_ids.sort()
        
        # Create a unique string combining player IDs and match date
        unique_string = f"{'-'.join(player_ids)}_{match.get('match_date', '')}"
        
        # Use a hash of this string as the match ID
        return hashlib.md5(unique_string.encode()).hexdigest()

    def is_custom_game_between_players(self, match: Dict[str, Any], registered_players: List[Dict[str, Any]]) -> bool:
        """Check if a match is a custom game between registered players"""
        # Get all player IDs from the match
        match_players = []
        for player in match.get('axis_players', []) + match.get('allies_players', []):
            match_players.append(player.get('player_id'))
        
        # Get all registered player IDs
        registered_player_ids = [p['player_id'] for p in registered_players]
        
        # Check if all players in the match are registered players
        all_players_registered = all(player_id in registered_player_ids for player_id in match_players)
        
        # Check if it's a custom game
        is_custom = 'custom' in match.get('match_type', '').lower()
        
        return is_custom and all_players_registered

    def is_auto_match_with_registered_player(self, match: Dict[str, Any], registered_players: List[Dict[str, Any]]) -> bool:
        """Check if a match is an auto match with at least one registered player"""
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
        
        return is_not_custom and any_player_registered

    def extract_matches_from_page(self, page, player_id: str, player_name: str) -> List[Dict[str, Any]]:
        """Extract match data from the page"""
        matches = []
        
        # Wait for the table to be visible
        page.wait_for_selector("table", timeout=10000)
        
        # Extract match data from __NEXT_DATA__
        next_data = page.evaluate("""() => {
            const nextDataElement = document.getElementById('__NEXT_DATA__');
            if (nextDataElement) {
                try {
                    return JSON.parse(nextDataElement.textContent);
                } catch (e) {
                    return null;
                }
            }
            return null;
        }""")
        
        if next_data:
            # Try to extract match data from next_data
            try:
                # The path to the matches data might vary, so we need to explore the structure
                page_props = next_data.get("props", {}).get("pageProps", {})
                
                # Try different paths where match data might be located
                recent_matches = None
                for path in ['recentMatches', 'playerDataAPI.recentMatches', 'matches', 'playerDataAPI.matches']:
                    data = page_props
                    for key in path.split('.'):
                        data = data.get(key, {})
                    if data:
                        recent_matches = data
                        break
                
                if recent_matches:
                    # Process each match
                    for match_data in recent_matches:
                        try:
                            # Extract basic match information
                            match_id = match_data.get("id") or match_data.get("matchId")
                            if not match_id:
                                match_id = f"next_{int(datetime.now().timestamp())}_{hash(str(match_data))}"
                            
                            # Extract other match data
                            match_date = match_data.get("date") or match_data.get("matchDate")
                            if not match_date:
                                timestamp = match_data.get("timestamp") or match_data.get("startTime")
                                if timestamp:
                                    match_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                                else:
                                    match_date = "Unknown"
                            
                            match_type = match_data.get("type") or match_data.get("matchType") or "Unknown"
                            match_result = match_data.get("result") or match_data.get("outcome") or "Unknown"
                            map_name = match_data.get("map") or match_data.get("mapName") or "Unknown"
                            
                            # Extract players
                            axis_players = []
                            allies_players = []
                            players_data = match_data.get("players") or match_data.get("members") or []
                            
                            for player_data in players_data:
                                if isinstance(player_data, dict):
                                    player_info = {
                                        "player_id": str(player_data.get("id") or player_data.get("profile_id")),
                                        "player_name": player_data.get("name") or player_data.get("profile", {}).get("name")
                                    }
                                    
                                    # Determine team based on faction or side
                                    if player_data.get("faction") == "axis" or player_data.get("side") == "axis":
                                        axis_players.append(player_info)
                                    else:
                                        allies_players.append(player_info)
                            
                            # Create processed match
                            processed_match = {
                                "match_id": match_id,
                                "player_id": player_id,
                                "player_name": player_name,
                                "match_date": match_date,
                                "match_type": match_type,
                                "match_result": match_result,
                                "map_name": map_name,
                                "axis_players": axis_players,
                                "allies_players": allies_players,
                                "is_simulated": False,
                                "is_scraped": True,
                                "scraped_at": datetime.now().isoformat()
                            }
                            
                            matches.append(processed_match)
                            
                        except Exception as e:
                            logger.error(f"Error processing match: {str(e)}")
                            continue
            except Exception as e:
                logger.error(f"Error extracting matches from __NEXT_DATA__: {str(e)}")
        
        # If we still don't have matches, try to extract from the table directly
        if not matches:
            logger.info("Extracting matches from table...")
            table_rows = page.query_selector_all("table tr")
            
            if table_rows:
                # Skip header row
                for i, row in enumerate(table_rows[1:], 1):
                    try:
                        cells = row.query_selector_all("td")
                        if len(cells) >= 6:
                            match_date = cells[0].text_content().strip()
                            match_result = cells[1].text_content().strip()
                            axis_players = [{"player_name": name.strip()} for name in cells[2].text_content().strip().split(",")]
                            allies_players = [{"player_name": name.strip()} for name in cells[3].text_content().strip().split(",")]
                            map_name = cells[4].text_content().strip()
                            match_type = cells[5].text_content().strip()
                            
                            processed_match = {
                                "match_id": f"table_{player_id}_{i}",
                                "player_id": player_id,
                                "player_name": player_name,
                                "match_date": match_date,
                                "match_type": match_type,
                                "match_result": match_result,
                                "map_name": map_name,
                                "axis_players": axis_players,
                                "allies_players": allies_players,
                                "is_simulated": False,
                                "is_scraped": True,
                                "scraped_at": datetime.now().isoformat()
                            }
                            
                            matches.append(processed_match)
                    except Exception as e:
                        logger.error(f"Error processing table row {i}: {str(e)}")
                        continue
        
        return matches

    def extract_player_matches(self, player_id: str, player_name: str) -> List[Dict[str, Any]]:
        """Extract matches for a specific player using Playwright"""
        url = f"https://coh3stats.com/players/{player_id}/{player_name}/matches?view=recentMatches"
        logger.info(f"Extracting matches for {player_name} from {url}")
        
        with sync_playwright() as p:
            # Launch browser with slower network and viewport
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            try:
                # Navigate to the URL
                page.goto(url)
                page.wait_for_load_state("networkidle")
                
                # Extract matches
                matches = self.extract_matches_from_page(page, player_id, player_name)
                logger.info(f"Found {len(matches)} matches for {player_name}")
                
                return matches
            except Exception as e:
                logger.error(f"Error extracting matches for {player_name}: {str(e)}")
                return []
            finally:
                browser.close()

    def process_matches(self, matches: List[Dict[str, Any]], registered_players: List[Dict[str, Any]]) -> tuple:
        """Process matches and store them in appropriate collections"""
        new_custom_games = 0
        new_auto_matches = 0
        
        for match in matches:
            # Generate unique match ID
            unique_match_id = self.generate_unique_match_id(match)
            match['unique_match_id'] = unique_match_id
            
            # Check if it's a custom game between registered players
            if self.is_custom_game_between_players(match, registered_players):
                if not self.custom_games_collection.find_one({"unique_match_id": unique_match_id}):
                    match['discovered_at'] = datetime.now()
                    self.custom_games_collection.insert_one(match)
                    new_custom_games += 1
                    logger.info(f"New custom game found: {match['match_id']}")
            
            # Check if it's an auto match with at least one registered player
            elif self.is_auto_match_with_registered_player(match, registered_players):
                if not self.auto_matches_collection.find_one({"unique_match_id": unique_match_id}):
                    match['discovered_at'] = datetime.now()
                    self.auto_matches_collection.insert_one(match)
                    new_auto_matches += 1
                    logger.info(f"New auto match found: {match['match_id']}")
        
        return new_custom_games, new_auto_matches

    def check_for_new_games(self):
        """Check for new games for a batch of players"""
        logger.info("Starting check for new games")
        
        # Get batch of players to analyze
        players_batch = self.get_players_to_analyze()
        if not players_batch:
            logger.warning("No players registered in the database")
            return
        
        # Get all registered players for validation
        all_registered_players = list(self.players_collection.find({}))
        
        total_custom_games = 0
        total_auto_matches = 0
        
        # Check each player in the batch
        for player in players_batch:
            player_id = player["player_id"]
            player_name = player["player_name"]
            
            try:
                # Extract matches for this player
                matches = self.extract_player_matches(player_id, player_name)
                
                # Process and store matches
                new_custom_games, new_auto_matches = self.process_matches(matches, all_registered_players)
                total_custom_games += new_custom_games
                total_auto_matches += new_auto_matches
                
                # Update last check time
                self.last_check_times[player_id] = datetime.now()
                
                # Wait between players to avoid overloading
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing player {player_name}: {str(e)}")
                continue
        
        logger.info(f"Found {total_custom_games} new custom games and {total_auto_matches} new auto matches")

    def run(self):
        """Run the game monitor service"""
        logger.info(f"Starting Game Monitor Service (check interval: {CHECK_INTERVAL} seconds)")
        
        while True:
            try:
                start_time = time.time()
                self.check_for_new_games()
                execution_time = time.time() - start_time
                
                # Calculate sleep time (ensure minimum 1 minute between checks)
                sleep_time = max(CHECK_INTERVAL - execution_time, 60)
                logger.info(f"Execution took {execution_time:.1f} seconds")
                logger.info(f"Waiting {sleep_time/60:.1f} minutes before next batch...")
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                logger.info(f"Waiting {ERROR_WAIT_TIME} seconds before retrying...")
                time.sleep(ERROR_WAIT_TIME) 