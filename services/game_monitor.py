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
    
    def extract_matches_from_page(self, page, player_id, player_name, is_first_check=False):
        """Extract match data from the page"""
        logger.debug(f"Extracting matches for {player_name} (first check: {is_first_check})")
        matches = []
        
        try:
            # Wait for the match table to be visible
            page.wait_for_selector('table', timeout=30000)
            
            # Get the page content
            content = page.content()
            
            # Save page content for debugging
            debug_file = f"page_content_{player_name}.html"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(content)
            logger.debug(f"Saved page content to {debug_file}")
            
            # Try to get __NEXT_DATA__
            next_data = page.evaluate('''() => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? JSON.parse(el.textContent) : null;
            }''')
            
            if next_data:
                debug_file = f"nextdata_{player_name}.json"
                with open(debug_file, "w", encoding="utf-8") as f:
                    json.dump(next_data, f, indent=2)
                logger.debug(f"Saved __NEXT_DATA__ to {debug_file}")
                
                # Extract matches from next_data
                try:
                    # Try different paths where match data might be located
                    matches_data = None
                    page_props = next_data.get("props", {}).get("pageProps", {})
                    
                    # Log available keys for debugging
                    logger.debug(f"Available keys in pageProps: {list(page_props.keys())}")
                    
                    if "matches" in page_props:
                        matches_data = page_props["matches"]
                    elif "recentMatches" in page_props:
                        matches_data = page_props["recentMatches"]
                    elif "playerDataAPI" in page_props:
                        player_data = page_props["playerDataAPI"]
                        if "matches" in player_data:
                            matches_data = player_data["matches"]
                        elif "recentMatches" in player_data:
                            matches_data = player_data["recentMatches"]
                    
                    if matches_data:
                        logger.info(f"Found {len(matches_data)} matches in __NEXT_DATA__")
                        for match_data in matches_data:
                            try:
                                # Extract match details
                                match_id = match_data.get("matchId") or match_data.get("id")
                                match_type = match_data.get("matchtype", "Unknown")
                                match_date = datetime.fromtimestamp(
                                    match_data.get("completiontime") or 
                                    match_data.get("startgametime") or 
                                    time.time()
                                ).isoformat()
                                
                                # Extract players
                                axis_players = []
                                allies_players = []
                                for player in match_data.get("matchhistoryreportresults", []):
                                    player_info = {
                                        "player_id": str(player.get("profile_id")),
                                        "player_name": player.get("profile", {}).get("name")
                                    }
                                    # Determine team based on race_id
                                    if player.get("race_id") in [0, 3]:  # Wehrmacht or DAK
                                        axis_players.append(player_info)
                                    else:  # US Forces or British Forces
                                        allies_players.append(player_info)
                                
                                # Create match object
                                match = {
                                    "match_id": match_id,
                                    "player_id": player_id,
                                    "player_name": player_name,
                                    "match_date": match_date,
                                    "match_type": match_type,
                                    "map_name": match_data.get("mapname", "Unknown"),
                                    "axis_players": axis_players,
                                    "allies_players": allies_players,
                                    "is_custom": match_type == 0,
                                    "discovered_at": datetime.now().isoformat()
                                }
                                matches.append(match)
                                logger.debug(f"Processed match {match_id}")
                            
                            except Exception as e:
                                logger.error(f"Error processing match: {str(e)}")
                                continue
                
                except Exception as e:
                    logger.error(f"Error processing __NEXT_DATA__: {str(e)}")
            
            # If no matches found from __NEXT_DATA__, try extracting from table
            if not matches:
                logger.info("No matches found in __NEXT_DATA__, trying table extraction")
                # Get all rows from the match table
                rows = page.query_selector_all('table tr')
                if len(rows) > 1:  # Skip header row
                    logger.info(f"Found {len(rows)-1} rows in match table")
                    for row in rows[1:]:  # Skip header row
                        try:
                            # Extract match data from row
                            cells = row.query_selector_all('td')
                            if len(cells) >= 6:
                                # Extract match details from cells
                                match = {
                                    "match_id": hashlib.md5(row.inner_text().encode()).hexdigest(),
                                    "player_id": player_id,
                                    "player_name": player_name,
                                    "match_date": cells[0].inner_text(),
                                    "match_type": cells[5].inner_text().split()[0],
                                    "map_name": cells[4].inner_text(),
                                    "axis_players": self.extract_players_from_cell(cells[2]),
                                    "allies_players": self.extract_players_from_cell(cells[3]),
                                    "discovered_at": datetime.now().isoformat()
                                }
                                matches.append(match)
                                logger.debug(f"Processed match from table row")
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
    
    def extract_players_from_cell(self, cell):
        """Extract player information from a table cell"""
        players = []
        try:
            # Find all player links in the cell
            player_links = cell.query_selector_all('a')
            for link in player_links:
                href = link.get_attribute('href') or ""
                player_id_match = re.search(r'/players/(\d+)', href)
                if player_id_match:
                    player_id = player_id_match.group(1)
                    player_name = link.inner_text().strip()
                    players.append({
                        "player_id": player_id,
                        "player_name": player_name
                    })
        except Exception as e:
            logger.error(f"Error extracting players from cell: {str(e)}")
        return players
    
    def get_player_matches(self, player_id, player_name):
        """Get matches for a specific player"""
        is_first_check = self.last_check_times.get(player_id) is None
        logger.info(f"Getting matches for {player_name} (first check: {is_first_check})")
        matches = []
        
        try:
            with sync_playwright() as p:
                # Launch browser with slower network to ensure page loads
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox']
                )
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
                )
                page = context.new_page()
                
                # For first-time checks, get all available matches
                if is_first_check:
                    logger.info(f"Performing first-time check for {player_name}")
                    # Navigate to the all matches page
                    url = f"https://coh3stats.com/players/{player_id}/{player_name}/matches"
                    logger.info(f"Navigating to all matches: {url}")
                    page.goto(url)
                    matches.extend(self.extract_matches_from_page(page, player_id, player_name, True))
                
                # Always check recent matches
                url = f"https://coh3stats.com/players/{player_id}/{player_name}/matches?view=recentMatches"
                logger.info(f"Navigating to recent matches: {url}")
                page.goto(url)
                recent_matches = self.extract_matches_from_page(page, player_id, player_name, False)
                
                # Merge matches, avoiding duplicates
                existing_ids = {m["match_id"] for m in matches}
                for match in recent_matches:
                    if match["match_id"] not in existing_ids:
                        matches.append(match)
                        existing_ids.add(match["match_id"])
                
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
                        # Generate unique match ID
                        unique_id = hashlib.md5(
                            f"{match['match_date']}_{match['player_id']}_{match['match_type']}".encode()
                        ).hexdigest()
                        match['unique_match_id'] = unique_id
                        
                        # Determine if it's a custom game
                        is_custom = match.get('is_custom') or 'custom' in match['match_type'].lower()
                        
                        if is_custom:
                            # Check if match already exists
                            if not self.custom_games_collection.find_one({"unique_match_id": unique_id}):
                                self.custom_games_collection.insert_one(match)
                                logger.info(f"Saved new custom game: {unique_id}")
                        else:
                            # Check if match already exists
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