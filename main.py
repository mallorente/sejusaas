import requests
from bs4 import BeautifulSoup
import pymongo
from datetime import datetime, timedelta
import time
import os
import re
import json
import random
from dotenv import load_dotenv
from fetch_real_matches import COH3RealMatchFetcher

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://usuario:contraseña@cluster0.mongodb.net/")
DB_NAME = "coh3stats_db"
PLAYERS_COLLECTION = "players"
MATCHES_COLLECTION = "matches"
CUSTOM_GAMES_COLLECTION = "custom_games"

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
        # Connect to MongoDB
        self.client = pymongo.MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.players_collection = self.db[PLAYERS_COLLECTION]
        self.matches_collection = self.db[MATCHES_COLLECTION]
        self.custom_games_collection = self.db[CUSTOM_GAMES_COLLECTION]
        
        # Initialize the real match fetcher
        self.real_match_fetcher = COH3RealMatchFetcher()
        
    def get_players_to_analyze(self):
        """Get the list of players to analyze from the database"""
        return list(self.players_collection.find({}))
    
    def add_player(self, player_id, player_name):
        """Add a new player to the database"""
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
        print(f"Player {player_name} (ID: {player_id}) added successfully")
    
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
        Get real match data by extracting it from the HTML table on the player's page
        
        This is an alternative to the simulate_recent_matches function that uses real data
        """
        print(f"Getting real match data for player: {player_name} (ID: {player_id})")
        
        # First, we need to get the HTML page
        html_file_path = f"sejusaas/player_page_playwright_{player_name}.html"
        
        # Check if file exists, try alternative paths if not
        if not os.path.exists(html_file_path):
            print(f"File not found at {html_file_path}, trying alternative paths...")
            alternative_paths = [
                f"player_page_playwright_{player_name}.html",
                f"sejusaas/player_page_{player_name}.html",
                f"player_page_{player_name}.html"
            ]
            for path in alternative_paths:
                if os.path.exists(path):
                    html_file_path = path
                    print(f"Found file at {html_file_path}")
                    break
        
        if not os.path.exists(html_file_path):
            print(f"No HTML file found for player {player_name}")
            return []
        
        # Extract match data from the HTML
        matches = self.extract_match_data_from_table(html_file_path, player_id, player_name)
        
        # Save matches to a JSON file for reference
        output_file = f"matches_table_{player_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(matches, f, indent=2)
        
        return matches
    
    def extract_match_data_from_table(self, html_file_path, player_id, player_name):
        """
        Extract match data from the HTML table in the player page
        """
        print(f"Extracting match data from {html_file_path}")
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the match table
        match_table = soup.find('table')
        if not match_table:
            print("No match table found in the HTML")
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
                date_text = date_cell.find('p', {'data-inherit': 'true'}).text.strip()
                
                # Extract match result
                result_cell = cells[1]
                result_div = result_cell.find('div', {'class': 'matches-table_row-indicator__30FKJ'})
                if result_div and 'win-indicator' in result_div.get('class', []):
                    match_result = "Victory"
                else:
                    match_result = "Defeat"
                
                # Extract rating change
                rating_badge = result_cell.find('div', {'class': 'm_347db0ec'})
                rating_change = rating_badge.text.strip() if rating_badge else "Unknown"
                
                # Extract map
                map_cell = cells[4]
                map_name = map_cell.find('p', {'data-size': 'sm'}).text.strip()
                
                # Extract game mode and duration
                mode_cell = cells[5]
                mode_div = mode_cell.find('div', {'style': 'white-space: nowrap;'})
                mode = mode_div.text.strip() if mode_div else "Unknown"
                duration = mode_cell.find('span').text.strip()
                
                # Extract axis players
                axis_cell = cells[2]
                axis_players = []
                for player_div in axis_cell.find_all('div', recursive=False):
                    player_link = player_div.find('a')
                    if player_link:
                        player_href = player_link.get('href', '')
                        player_id_match = re.search(r'/players/(\d+)', player_href)
                        if player_id_match:
                            player_id_from_link = player_id_match.group(1)
                            player_name_span = player_link.find('span', {'class': ''})
                            if player_name_span:
                                player_name_from_link = player_name_span.text.strip()
                                axis_players.append({
                                    'player_id': player_id_from_link,
                                    'player_name': player_name_from_link
                                })
                
                # Extract allies players
                allies_cell = cells[3]
                allies_players = []
                for player_div in allies_cell.find_all('div', recursive=False):
                    player_link = player_div.find('a')
                    if player_link:
                        player_href = player_link.get('href', '')
                        player_id_match = re.search(r'/players/(\d+)', player_href)
                        if player_id_match:
                            player_id_from_link = player_id_match.group(1)
                            player_name_span = player_link.find('span', {'class': ''})
                            if player_name_span:
                                player_name_from_link = player_name_span.text.strip()
                                allies_players.append({
                                    'player_id': player_id_from_link,
                                    'player_name': player_name_from_link
                                })
                
                # Generate a unique match ID
                match_id = f"{player_id}_{len(matches)}"
                
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
                    'is_scraped': True
                }
                
                matches.append(match)
                
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
        
        print(f"Found {len(matches)} matches")
        return matches
    
    def get_real_matches(self, player_id, player_name, days_back=7):
        """
        Get real match data for a player
        
        This replaces the simulate_recent_matches function with real data
        """
        # First try to get matches from HTML table
        matches = self.get_real_matches_from_html(player_id, player_name)
        
        # If that fails, fall back to the API method
        if not matches:
            print("No matches found in HTML, falling back to API method")
            matches = self.real_match_fetcher.fetch_matches_for_player(player_id, player_name, days_back)
        
        return matches
    
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
    
    def find_custom_games_between_players(self):
        """
        Find custom games between registered players
        and save them in the custom games collection
        """
        return self.real_match_fetcher.find_custom_games_between_players()
    
    def get_custom_games(self):
        """Get all saved custom games"""
        return list(self.custom_games_collection.find().sort("discovered_at", pymongo.DESCENDING))

def main():
    analyzer = COH3StatsAnalyzer()
    
    while True:
        try:
            # Analyze all players
            analyzer.analyze_all_players()
            
            # Find custom games between players
            analyzer.find_custom_games_between_players()
            
            # Wait 1 hour before the next execution
            print("Waiting 1 hour before next update...")
            time.sleep(3600)
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(60)  # Wait 1 minute if there's an error

if __name__ == "__main__":
    main() 