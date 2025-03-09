import requests
import json
import time
from datetime import datetime, timedelta
import os
import pymongo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://usuario:contraseña@cluster0.mongodb.net/")
DB_NAME = "coh3stats_db"
PLAYERS_COLLECTION = "players"
MATCHES_COLLECTION = "matches"
CUSTOM_GAMES_COLLECTION = "custom_games"

class COH3RealMatchFetcher:
    def __init__(self):
        # Connect to MongoDB
        self.client = pymongo.MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.players_collection = self.db[PLAYERS_COLLECTION]
        self.matches_collection = self.db[MATCHES_COLLECTION]
        self.custom_games_collection = self.db[CUSTOM_GAMES_COLLECTION]
        
        # Base URL for COH3Stats open data API
        self.base_url = "https://storage.coh3stats.com/matches/matches-{timestamp}.json"
        
    def get_players_to_analyze(self):
        """Get the list of players to analyze from the database"""
        return list(self.players_collection.find({}))
    
    def get_unix_timestamp_for_date(self, date):
        """Get the Unix timestamp for a given date at 00:00:00 UTC"""
        # Create a datetime object at 00:00:00 UTC for the given date
        utc_date = datetime(date.year, date.month, date.day, 0, 0, 0)
        # Convert to timestamp (seconds since epoch)
        timestamp = int(utc_date.timestamp())
        return timestamp
    
    def fetch_matches_for_date(self, date):
        """Fetch matches for a specific date from COH3Stats open data API"""
        timestamp = self.get_unix_timestamp_for_date(date)
        url = self.base_url.format(timestamp=timestamp)
        
        try:
            print(f"Fetching matches for {date.strftime('%Y-%m-%d')} from {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            # Save raw data for debugging
            with open(f"matches_raw_{timestamp}.json", "w") as f:
                json.dump(data, f)
                
            return data.get("matches", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching matches for {date.strftime('%Y-%m-%d')}: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for {date.strftime('%Y-%m-%d')}: {str(e)}")
            return []
    
    def process_match_data(self, match, player_profiles):
        """Process raw match data into a more usable format"""
        # Extract basic match information
        match_id = match.get("id")
        map_name = match.get("mapname", "Unknown Map")
        match_type_id = match.get("matchtype_id")
        start_time = match.get("startgametime")
        completion_time = match.get("completiontime")
        
        # Determine match type based on matchtype_id
        match_type = "Unknown"
        if match_type_id == 1:
            match_type = "Ranked 1v1"
        elif match_type_id == 2:
            match_type = "Ranked 2v2"
        elif match_type_id == 3:
            match_type = "Ranked 3v3"
        elif match_type_id == 4:
            match_type = "Ranked 4v4"
        elif match_type_id == 0:
            match_type = "Custom Game"
        
        # Convert Unix timestamp to datetime string
        match_date = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M")
        
        # Extract player information
        players = []
        player_results = {}
        
        for report in match.get("matchhistoryreportresults", []):
            profile_id = report.get("profile_id")
            profile = report.get("profile", {})
            player_name = profile.get("name", "Unknown")
            
            # Store player result
            result_type = report.get("resulttype")
            result = "Victory" if result_type == 1 else "Defeat" if result_type == 2 else "Unknown"
            player_results[str(profile_id)] = result
            
            # Add player to the list
            players.append(player_name)
        
        # Create processed match data
        processed_match = {
            "match_id": match_id,
            "map_name": map_name,
            "match_type": match_type,
            "match_date": match_date,
            "players": players,
            "player_results": player_results,
            "is_simulated": False,
            "scraped_at": datetime.now()
        }
        
        return processed_match
    
    def fetch_matches_for_player(self, player_id, player_name, days_back=7):
        """Fetch and process matches for a specific player"""
        print(f"Fetching matches for player: {player_name} (ID: {player_id})")
        
        # Get all players for reference
        all_players = {p["player_id"]: p["player_name"] for p in self.get_players_to_analyze()}
        
        # Fetch matches for the last X days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        current_date = start_date
        all_matches = []
        player_matches = []
        
        while current_date <= end_date:
            # Fetch matches for the current date
            matches = self.fetch_matches_for_date(current_date)
            
            # Process each match
            for match in matches:
                # Check if the player is in this match
                player_ids = [str(report.get("profile_id")) for report in match.get("matchhistoryreportresults", [])]
                
                if str(player_id) in player_ids:
                    # Process the match
                    processed_match = self.process_match_data(match, all_players)
                    
                    # Add player-specific information
                    for report in match.get("matchhistoryreportresults", []):
                        if str(report.get("profile_id")) == str(player_id):
                            result_type = report.get("resulttype")
                            processed_match["match_result"] = "Victory" if result_type == 1 else "Defeat" if result_type == 2 else "Unknown"
                            processed_match["player_id"] = player_id
                            processed_match["player_name"] = player_name
                    
                    # Add to player matches
                    player_matches.append(processed_match)
                
                # Add to all matches
                all_matches.append(match)
            
            # Move to the next day
            current_date += timedelta(days=1)
            
            # Sleep to avoid overwhelming the API
            time.sleep(1)
        
        print(f"Found {len(player_matches)} matches for {player_name}")
        return player_matches
    
    def save_matches_to_db(self, matches):
        """Save processed matches to the database"""
        for match in matches:
            # Check if the match already exists
            if not self.matches_collection.find_one({"match_id": match["match_id"]}):
                self.matches_collection.insert_one(match)
                print(f"New match saved: {match['match_id']}")
    
    def find_custom_games_between_players(self):
        """Find custom games between registered players and save them"""
        players = self.get_players_to_analyze()
        
        if not players:
            print("No players in the database to analyze")
            return []
        
        # Get player names for comparison
        player_names = [p["player_name"].lower() for p in players]
        
        custom_games = []
        processed_match_ids = set()
        
        # Find custom games in the matches collection
        custom_matches = self.matches_collection.find({
            "match_type": "Custom Game",
            "is_simulated": False
        }).sort("match_date", pymongo.DESCENDING).limit(50)
        
        for match in custom_matches:
            match_id = match["match_id"]
            
            # Avoid processing the same match multiple times
            if match_id in processed_match_ids:
                continue
            
            # Check if there are at least two registered players in the match
            match_players = [p.lower() for p in match.get("players", [])]
            registered_players_in_match = [p for p in match_players if p in player_names]
            
            if len(registered_players_in_match) >= 2:
                # This is a custom game between registered players
                custom_game = {
                    "match_id": match_id,
                    "match_date": match["match_date"],
                    "match_type": match["match_type"],
                    "map_name": match["map_name"],
                    "players": registered_players_in_match,
                    "discovered_by": match["player_name"],
                    "discovered_at": datetime.now(),
                    "is_simulated": False
                }
                
                # Save to database if it doesn't exist
                if not self.custom_games_collection.find_one({"match_id": match_id}):
                    self.custom_games_collection.insert_one(custom_game)
                    print(f"New custom game found: {match_id}")
                    custom_games.append(custom_game)
                
                processed_match_ids.add(match_id)
        
        return custom_games
    
    def analyze_all_players(self, days_back=7):
        """Analyze recent matches for all players in the database"""
        players = self.get_players_to_analyze()
        
        if not players:
            print("No players in the database to analyze")
            return
        
        for player in players:
            player_id = player["player_id"]
            player_name = player["player_name"]
            
            # Fetch and process matches for this player
            matches = self.fetch_matches_for_player(player_id, player_name, days_back)
            
            # Save matches to the database
            self.save_matches_to_db(matches)
            
            # Update player information
            self.players_collection.update_one(
                {"player_id": player_id},
                {"$set": {
                    "last_analyzed": datetime.now(),
                    "matches_found": len(matches)
                }}
            )
            
            # Sleep to avoid overwhelming the API
            time.sleep(2)
        
        # Find custom games between players
        self.find_custom_games_between_players()

def main():
    fetcher = COH3RealMatchFetcher()
    
    while True:
        try:
            # Analyze all players
            fetcher.analyze_all_players(days_back=7)
            
            # Wait 1 hour before the next execution
            print("Waiting 1 hour before next update...")
            time.sleep(3600)
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(60)  # Wait 1 minute if there's an error

if __name__ == "__main__":
    main() 