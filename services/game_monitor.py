"""Game Monitor Service for tracking COH3 games"""

import os
import logging
import pymongo
from datetime import datetime, timedelta
import time
import hashlib
from playwright.sync_api import sync_playwright
import json
import re
from typing import List, Dict, Any
from dotenv import load_dotenv

# Import the SheetsExporter
from .sheets_exporter import SheetsExporter

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class GameMonitorService:
    def __init__(self, mongo_uri=None, check_interval=900):
        """Initialize the game monitor service"""
        self.mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/coh3stats_db")
        self.check_interval = int(os.getenv("CHECK_INTERVAL", check_interval))
        self.db_name = "coh3stats_db"
        
        # Connect to MongoDB
        try:
            self.client = pymongo.MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.players_collection = self.db["players"]
            self.custom_games_collection = self.db["custom_games"]
            self.auto_matches_collection = self.db["auto_matches"]
            logger.info(f"Connected to MongoDB database: {self.db_name}")
        except Exception as e:
            logger.critical(f"Failed to connect to MongoDB: {str(e)}")
            raise
        
        # Track last check time for each player
        self.last_check_times = {}
        
        # Initialize the sheets exporter
        self.sheets_exporter = SheetsExporter()
        if self.sheets_exporter.is_connected():
            logger.info("Google Sheets exporter initialized successfully")
        else:
            logger.warning("Google Sheets exporter not connected. Export to sheets will be disabled.")
            
        logger.info("Game Monitor Service initialized")
    
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
                # For new players, set last check time to None to indicate first check
                self.last_check_times[player_id] = None
                logger.debug(f"First-time check for player {player['player_name']} (ID: {player_id})")
        
        # Sort players by last check time (None values first, then oldest)
        players.sort(key=lambda p: (
            self.last_check_times.get(p['player_id']) is not None,
            self.last_check_times.get(p['player_id']) or datetime.min
        ))
        
        # Return first 5 players
        batch = players[:5]
        logger.info(f"Selected batch of {len(batch)} players to analyze")
        return batch
    
    def extract_matches_from_page(self, page, player_id, player_name):
        """Extract match data from the page using the proven approach"""
        logger.debug(f"Extracting matches for {player_name}")
        matches = []
        
        try:
            # Wait for the match table to be visible
            logger.debug("Waiting for match table to be visible")
            page.wait_for_selector('table', timeout=30000)
            
            # Get __NEXT_DATA__ content
            logger.debug("Attempting to extract __NEXT_DATA__")
            next_data = page.evaluate('''() => {
                const el = document.getElementById('__NEXT_DATA__');
                if (!el) return null;
                try {
                    return JSON.parse(el.textContent);
                } catch (e) {
                    return null;
                }
            }''')
            
            if next_data:
                # Save for debugging
                debug_file = f"nextdata_{player_name}.json"
                with open(debug_file, "w", encoding="utf-8") as f:
                    json.dump(next_data, f, indent=2)
                logger.debug(f"Saved __NEXT_DATA__ to {debug_file}")
                
                # Process matches from next_data
                page_props = next_data.get("props", {}).get("pageProps", {})
                logger.debug(f"Available keys in pageProps: {list(page_props.keys())}")
                
                # Try to find matches data
                matches_data = None
                
                # Check different possible paths
                if "matches" in page_props:
                    matches_data = page_props["matches"]
                elif "recentMatches" in page_props:
                    matches_data = page_props["recentMatches"]
                elif "playerDataAPI" in page_props:
                    player_data = page_props["playerDataAPI"]
                    if isinstance(player_data, dict):
                        if "matches" in player_data:
                            matches_data = player_data["matches"]
                        elif "recentMatches" in player_data:
                            matches_data = player_data["recentMatches"]
                
                # Try dehydratedState as last resort
                if not matches_data and "dehydratedState" in next_data:
                    dehydrated = next_data["dehydratedState"]
                    if "queries" in dehydrated:
                        for query in dehydrated["queries"]:
                            if "state" in query and "data" in query["state"]:
                                data = query["state"]["data"]
                                if isinstance(data, dict):
                                    if "matches" in data:
                                        matches_data = data["matches"]
                                    elif "recentMatches" in data:
                                        matches_data = data["recentMatches"]
                
                if matches_data:
                    logger.info(f"Found {len(matches_data)} matches in __NEXT_DATA__")
                    for match_data in matches_data:
                        try:
                            # Extract match details
                            match_id = str(match_data.get("id", "")) or str(match_data.get("matchId", ""))
                            match_date = datetime.fromtimestamp(
                                match_data.get("completiontime", 0) or 
                                match_data.get("startgametime", 0) or 
                                time.time()
                            ).isoformat()
                            
                            # Extract players and determine teams
                            axis_players = []
                            allies_players = []
                            
                            for report in match_data.get("matchhistoryreportresults", []):
                                player_info = {
                                    "player_id": str(report.get("profile_id", "")),
                                    "player_name": report.get("profile", {}).get("name", "Unknown")
                                }
                                
                                # Determine team based on race_id
                                # 0 = Wehrmacht, 3 = DAK (Axis)
                                # 1 = US Forces, 2 = British Forces (Allies)
                                if report.get("race_id") in [0, 3]:
                                    axis_players.append(player_info)
                                else:
                                    allies_players.append(player_info)
                            
                            # Determine match type and result
                            match_type = "custom" if match_data.get("matchtype_id", 1) == 0 else "automatch"
                            result = "unknown"
                            for report in match_data.get("matchhistoryreportresults", []):
                                if str(report.get("profile_id", "")) == str(player_id):
                                    result_type = report.get("resulttype", -1)
                                    result = "victory" if result_type == 1 else "defeat" if result_type == 0 else "unknown"
                            
                            # Create match object
                            match = {
                                "match_id": match_id,
                                "player_id": player_id,
                                "player_name": player_name,
                                "match_date": match_date,
                                "match_type": match_type,
                                "match_result": result,
                                "map_name": match_data.get("mapname", "Unknown"),
                                "axis_players": axis_players,
                                "allies_players": allies_players,
                                "is_custom": match_type == "custom",
                                "discovered_at": datetime.now().isoformat()
                            }
                            
                            # Generate unique match ID
                            unique_id = hashlib.md5(
                                f"{match_date}_{match_id}_{match_type}".encode()
                            ).hexdigest()
                            match['unique_match_id'] = unique_id
                            
                            matches.append(match)
                            logger.debug(f"Processed match {match_id} ({match_type})")
                            
                        except Exception as e:
                            logger.error(f"Error processing match data: {str(e)}")
                            continue
            
            # If no matches found, try extracting from table
            if not matches:
                logger.info("No matches found in __NEXT_DATA__, trying table extraction")
                # Get all rows from the match table
                rows = page.query_selector_all('table tr')
                if len(rows) > 1:  # Skip header row
                    logger.info(f"Found {len(rows)-1} rows in match table")
                    for row in rows[1:]:  # Skip header row
                        try:
                            cells = row.query_selector_all('td')
                            if len(cells) >= 6:
                                # Extract date and time
                                date_text = cells[0].inner_text().strip()
                                
                                # Extract result and rating change
                                result_cell = cells[1]
                                result_div = result_cell.query_selector('.matches-table_row-indicator__30FKJ')
                                result = "victory" if result_div and "win-indicator" in result_div.get_attribute('class') else "defeat"
                                
                                # Extract map name
                                map_name = cells[4].inner_text().strip()
                                
                                # Extract game mode and duration
                                mode_cell = cells[5].inner_text().strip()
                                match_type = "custom" if "custom" in mode_cell.lower() else "automatch"
                                
                                # Extract players
                                axis_players = []
                                allies_players = []
                                
                                # Process axis players
                                axis_links = cells[2].query_selector_all('a')
                                for link in axis_links:
                                    href = link.get_attribute('href') or ""
                                    player_id_match = re.search(r'/players/(\d+)', href)
                                    if player_id_match:
                                        axis_players.append({
                                            "player_id": player_id_match.group(1),
                                            "player_name": link.inner_text().strip()
                                        })
                                
                                # Process allies players
                                allies_links = cells[3].query_selector_all('a')
                                for link in allies_links:
                                    href = link.get_attribute('href') or ""
                                    player_id_match = re.search(r'/players/(\d+)', href)
                                    if player_id_match:
                                        allies_players.append({
                                            "player_id": player_id_match.group(1),
                                            "player_name": link.inner_text().strip()
                                        })
                                
                                # Create match object
                                match = {
                                    "match_id": hashlib.md5(row.inner_text().encode()).hexdigest(),
                                    "player_id": player_id,
                                    "player_name": player_name,
                                    "match_date": date_text,
                                    "match_type": match_type,
                                    "match_result": result,
                                    "map_name": map_name,
                                    "axis_players": axis_players,
                                    "allies_players": allies_players,
                                    "is_custom": match_type == "custom",
                                    "discovered_at": datetime.now().isoformat()
                                }
                                
                                # Generate unique match ID
                                unique_id = hashlib.md5(
                                    f"{date_text}_{player_id}_{match_type}".encode()
                                ).hexdigest()
                                match['unique_match_id'] = unique_id
                                
                                matches.append(match)
                                logger.debug(f"Processed match from table ({match_type})")
                        except Exception as e:
                            logger.error(f"Error processing table row: {str(e)}")
                            continue
            
            # Take a screenshot if no matches found
            if not matches:
                screenshot_file = f"screenshot_{player_name}.png"
                page.screenshot(path=screenshot_file)
                logger.warning(f"No matches found for {player_name}, saved screenshot to {screenshot_file}")
            else:
                logger.info(f"Found {len(matches)} matches for {player_name}")
            
            return matches
            
        except Exception as e:
            logger.error(f"Error extracting matches: {str(e)}")
            return []
    
    def get_player_matches(self, player_id, player_name):
        """Get matches for a specific player"""
        is_first_check = self.last_check_times.get(player_id) is None
        logger.info(f"Getting matches for {player_name} (first check: {is_first_check})")
        matches = []
        
        try:
            with sync_playwright() as p:
                # Launch browser with Docker-specific configuration
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-gpu',
                        '--single-process'
                    ]
                )
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                
                # Set longer timeouts
                page.set_default_timeout(60000)  # 60 seconds
                page.set_default_navigation_timeout(60000)  # 60 seconds
                
                # Enable request interception to optimize page load
                def route_handler(route):
                    if route.request.resource_type in ["document", "script", "xhr", "fetch"]:
                        route.continue_()
                    else:
                        route.abort()
                
                page.route("**/*", route_handler)
                
                # Navigate to recent matches
                url = f"https://coh3stats.com/players/{player_id}/{player_name}/matches?view=recentMatches"
                logger.info(f"Navigating to: {url}")
                
                try:
                    # Navigate with retry logic
                    for attempt in range(3):
                        try:
                            response = page.goto(url, wait_until="networkidle")
                            if response and response.ok:
                                break
                            logger.warning(f"Navigation attempt {attempt + 1} failed, retrying...")
                            time.sleep(5)
                        except Exception as e:
                            if attempt == 2:  # Last attempt
                                raise
                            logger.warning(f"Navigation attempt {attempt + 1} failed: {str(e)}, retrying...")
                            time.sleep(5)
                    
                    # Save page content for debugging
                    page_content = page.content()
                    with open(f"page_content_{player_name}.html", "w", encoding="utf-8") as f:
                        f.write(page_content)
                    
                    # Extract matches
                    matches = self.extract_matches_from_page(page, player_id, player_name)
                    
                except Exception as e:
                    logger.error(f"Error during navigation: {str(e)}")
                    # Take screenshot on error
                    page.screenshot(path=f"error_{player_name}.png")
                    raise
                
                finally:
                    # Close browser
                    browser.close()
        
        except Exception as e:
            logger.error(f"Error getting matches for {player_name}: {str(e)}")
        
        return matches
    
    def check_for_new_games(self):
        """Check for new games from registered players"""
        logger.info("Checking for new games...")
        
        # Get batch of players to analyze
        players = self.get_players_to_analyze()
        if not players:
            logger.warning("No players registered in the database")
            return
        
        logger.info(f"Checking {len(players)} players")
        
        # Process each player
        for player in players:
            player_id = player["player_id"]
            player_name = player["player_name"]
            
            try:
                # Get matches for this player
                matches = self.get_player_matches(player_id, player_name)
                logger.info(f"Found {len(matches)} matches for {player_name}")
                
                # Process each match
                for match in matches:
                    try:
                        # Match already has unique_match_id from extraction
                        unique_id = match['unique_match_id']
                        
                        # Save to appropriate collection
                        if match['is_custom']:
                            if not self.custom_games_collection.find_one({"unique_match_id": unique_id}):
                                self.custom_games_collection.insert_one(match)
                                logger.info(f"Saved new custom game: {unique_id}")
                        else:
                            if not self.auto_matches_collection.find_one({"unique_match_id": unique_id}):
                                self.auto_matches_collection.insert_one(match)
                                logger.info(f"Saved new auto match: {unique_id}")
                    
                    except Exception as e:
                        logger.error(f"Error processing match: {str(e)}")
                        continue
                
                # Update last check time
                self.last_check_times[player_id] = datetime.now()
                
            except Exception as e:
                logger.error(f"Error processing player {player_name}: {str(e)}")
                continue
    
    def run(self):
        """Run the service"""
        logger.info("Starting Game Monitor Service")
        logger.info(f"Check interval: {self.check_interval} seconds")
        
        while True:
            try:
                # Check for new games
                start_time = time.time()
                self.check_for_new_games()
                execution_time = time.time() - start_time
                
                # Calculate sleep time (ensure minimum 1 minute between checks)
                sleep_time = max(self.check_interval - execution_time, 60)
                logger.info(f"Execution took {execution_time:.1f} seconds")
                logger.info(f"Waiting {sleep_time/60:.1f} minutes before next batch...")
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                logger.info("Waiting 60 seconds before retrying...")
                time.sleep(60)

    def process_matches(self, matches: List[Dict[str, Any]], registered_players: List[Dict[str, Any]]) -> tuple:
        """Process matches and store them in appropriate collections"""
        new_custom_games = 0
        new_auto_matches = 0
        custom_games_to_export = []
        
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
                    
                    # Add to list of games to export to sheets
                    custom_games_to_export.append(match)
            
            # Check if it's an auto match with at least one registered player
            elif self.is_auto_match_with_registered_player(match, registered_players):
                if not self.auto_matches_collection.find_one({"unique_match_id": unique_match_id}):
                    match['discovered_at'] = datetime.now()
                    self.auto_matches_collection.insert_one(match)
                    new_auto_matches += 1
                    logger.info(f"New auto match found: {match['match_id']}")
        
        # Export custom games to Google Sheets
        if custom_games_to_export and self.sheets_exporter.is_connected():
            try:
                exported_count = self.sheets_exporter.export_matches(custom_games_to_export)
                logger.info(f"Exported {exported_count} custom games to Google Sheets")
            except Exception as e:
                logger.error(f"Error exporting custom games to Google Sheets: {str(e)}")
        
        return new_custom_games, new_auto_matches 