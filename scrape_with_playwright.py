import asyncio
import json
import os
import time
from datetime import datetime
import pymongo
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://usuario:contraseña@cluster0.mongodb.net/")
DB_NAME = "coh3stats_db"
PLAYERS_COLLECTION = "players"
MATCHES_COLLECTION = "matches"
CUSTOM_GAMES_COLLECTION = "custom_games"

class PlaywrightScraper:
    def __init__(self):
        # Connect to MongoDB
        self.client = pymongo.MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.players_collection = self.db[PLAYERS_COLLECTION]
        self.matches_collection = self.db[MATCHES_COLLECTION]
        self.custom_games_collection = self.db[CUSTOM_GAMES_COLLECTION]
        
    def get_players_to_analyze(self):
        """Get the list of players to analyze from the database"""
        return list(self.players_collection.find({}))
    
    async def scrape_player_matches(self, player_id, player_name):
        """Scrape match data for a player using Playwright"""
        print(f"Scraping matches for player: {player_name} (ID: {player_id})")
        
        # URL for the player's recent matches
        url = f"https://coh3stats.com/players/{player_id}/{player_name}?view=recentMatches"
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Navigate to the URL
            print(f"Navigating to {url}")
            await page.goto(url)
            
            # Wait for the page to load
            await page.wait_for_load_state("networkidle")
            
            # Save the page content for debugging
            html_content = await page.content()
            with open(f"player_page_playwright_{player_name}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Extract match data
            matches = await self.extract_matches_from_page(page, player_id, player_name)
            
            # Close browser
            await browser.close()
            
            return matches
    
    async def extract_matches_from_page(self, page, player_id, player_name):
        """Extract match data from the page"""
        matches = []
        
        # First, try to extract data from the __NEXT_DATA__ script tag
        next_data = await page.evaluate("""() => {
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
            # Save the next_data for debugging
            with open(f"nextdata_playwright_{player_name}.json", "w", encoding="utf-8") as f:
                json.dump(next_data, f, indent=2)
            
            # Try to extract match data from next_data
            try:
                # The path to the matches data might vary, so we need to explore the structure
                page_props = next_data.get("props", {}).get("pageProps", {})
                
                # Check different possible locations for match data
                recent_matches = None
                
                # Try different paths where match data might be located
                if "recentMatches" in page_props:
                    recent_matches = page_props["recentMatches"]
                elif "playerDataAPI" in page_props and "recentMatches" in page_props["playerDataAPI"]:
                    recent_matches = page_props["playerDataAPI"]["recentMatches"]
                elif "playerData" in page_props and "recentMatches" in page_props["playerData"]:
                    recent_matches = page_props["playerData"]["recentMatches"]
                elif "matches" in page_props:
                    recent_matches = page_props["matches"]
                elif "playerDataAPI" in page_props and "matches" in page_props["playerDataAPI"]:
                    recent_matches = page_props["playerDataAPI"]["matches"]
                elif "playerData" in page_props and "matches" in page_props["playerData"]:
                    recent_matches = page_props["playerData"]["matches"]
                
                # Try to find matches in the dehydratedState
                if not recent_matches and "dehydratedState" in next_data:
                    dehydrated_state = next_data["dehydratedState"]
                    if "queries" in dehydrated_state:
                        for query in dehydrated_state["queries"]:
                            if "state" in query and "data" in query["state"]:
                                data = query["state"]["data"]
                                if isinstance(data, dict) and "matches" in data:
                                    recent_matches = data["matches"]
                                elif isinstance(data, dict) and "recentMatches" in data:
                                    recent_matches = data["recentMatches"]
                
                if recent_matches:
                    print(f"Found {len(recent_matches)} matches in __NEXT_DATA__")
                    
                    # Process each match
                    for match_data in recent_matches:
                        processed_match = self.process_match_data(match_data, player_id, player_name)
                        if processed_match:
                            matches.append(processed_match)
            except Exception as e:
                print(f"Error extracting matches from __NEXT_DATA__: {str(e)}")
        
        # If we couldn't extract data from __NEXT_DATA__, try to scrape it from the HTML
        if not matches:
            print("Trying to extract matches from HTML elements")
            
            # Try different selectors that might contain match data
            selectors = [
                ".match-item", 
                ".match-card", 
                "[data-match-id]",
                ".recent-matches .match-item",
                ".match-list .match-item",
                ".match-history .match-item",
                ".match-container",
                ".match",
                "tr.match",
                "div[role='row']",
                "table tr",
                ".mantine-Table-tr"
            ]
            
            for selector in selectors:
                print(f"Trying selector: {selector}")
                match_elements = await page.query_selector_all(selector)
                
                if match_elements:
                    print(f"Found {len(match_elements)} match elements with selector '{selector}'")
                    
                    for match_element in match_elements:
                        try:
                            # Extract match data from the element
                            match_id = await match_element.get_attribute("data-match-id")
                            if not match_id:
                                # Try to find match ID in a child element
                                id_element = await match_element.query_selector("[data-match-id]")
                                if id_element:
                                    match_id = await id_element.get_attribute("data-match-id")
                            
                            # If still no match ID, generate one
                            if not match_id:
                                match_id = f"html_{int(time.time())}_{len(matches)}"
                            
                            # Extract other match data
                            match_date_element = await match_element.query_selector(".match-date, .date, time, [data-date]")
                            match_date = await match_date_element.text_content() if match_date_element else "Unknown"
                            
                            match_type_element = await match_element.query_selector(".match-type, .type, [data-type]")
                            match_type = await match_type_element.text_content() if match_type_element else "Unknown"
                            
                            match_result_element = await match_element.query_selector(".match-result, .result, .victory, .defeat, [data-result]")
                            match_result = await match_result_element.text_content() if match_result_element else "Unknown"
                            
                            map_element = await match_element.query_selector(".map-name, .map, [data-map]")
                            map_name = await map_element.text_content() if map_element else "Unknown"
                            
                            # Extract players
                            player_elements = await match_element.query_selector_all(".player-name, .player, [data-player]")
                            players = []
                            for player_element in player_elements:
                                player_text = await player_element.text_content()
                                players.append(player_text.strip())
                            
                            # Create processed match
                            processed_match = {
                                "match_id": match_id,
                                "player_id": player_id,
                                "player_name": player_name,
                                "match_date": match_date,
                                "match_type": match_type,
                                "match_result": match_result,
                                "map_name": map_name,
                                "players": players,
                                "is_simulated": False,
                                "is_scraped_with_playwright": True,
                                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            matches.append(processed_match)
                        except Exception as e:
                            print(f"Error extracting match data from element: {str(e)}")
                    
                    # If we found matches with this selector, stop trying other selectors
                    if matches:
                        break
        
        # If we still don't have matches, try to take a screenshot for debugging
        if not matches:
            print("No matches found. Taking screenshot for debugging.")
            await page.screenshot(path=f"screenshot_{player_name}.png")
            
            # Try to extract data from the page content
            print("Trying to extract data from the page content")
            html_content = await page.content()
            
            # Look for match data in the HTML
            if "match-item" in html_content or "match-card" in html_content or "data-match-id" in html_content:
                print("Found match-related elements in the HTML, but couldn't extract them. Check the HTML file for debugging.")
            
            # Try to extract data from network requests
            print("Trying to extract data from network requests")
            await page.route("**/*", lambda route: route.continue_())
            await page.reload()
            await page.wait_for_load_state("networkidle")
            
            # Check if there are any API requests that might contain match data
            responses = []
            
            async def handle_response(response):
                if response.url.endswith(".json") or "api" in response.url:
                    try:
                        body = await response.text()
                        responses.append({"url": response.url, "body": body})
                    except:
                        pass
            
            page.on("response", handle_response)
            await page.wait_for_timeout(5000)  # Wait for 5 seconds to capture responses
            
            # Save responses for debugging
            for i, response in enumerate(responses):
                with open(f"response_{player_name}_{i}.json", "w", encoding="utf-8") as f:
                    f.write(response["body"])
                print(f"Saved response from {response['url']} to response_{player_name}_{i}.json")
        
        return matches
    
    def process_match_data(self, match_data, player_id, player_name):
        """Process match data from __NEXT_DATA__"""
        try:
            # Extract basic match information
            match_id = match_data.get("id") or match_data.get("matchId")
            if not match_id:
                match_id = f"next_{int(time.time())}_{hash(str(match_data))}"
            
            # Extract other match data
            match_date = match_data.get("date") or match_data.get("matchDate")
            if not match_date:
                # Try to extract from timestamp
                timestamp = match_data.get("timestamp") or match_data.get("startTime") or match_data.get("completionTime") or match_data.get("startgametime")
                if timestamp:
                    match_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    match_date = "Unknown"
            
            match_type = match_data.get("type") or match_data.get("matchType") or match_data.get("matchtype_id") or "Unknown"
            match_result = match_data.get("result") or match_data.get("outcome") or match_data.get("resulttype") or "Unknown"
            map_name = match_data.get("map") or match_data.get("mapName") or match_data.get("mapname") or "Unknown"
            
            # Extract players
            players = []
            players_data = match_data.get("players") or match_data.get("members") or match_data.get("matchhistoryreportresults") or []
            for player_data in players_data:
                if isinstance(player_data, dict):
                    player_name_field = player_data.get("name") or player_data.get("playerName")
                    if not player_name_field and "profile" in player_data:
                        profile = player_data.get("profile", {})
                        player_name_field = profile.get("name")
                    
                    if player_name_field:
                        players.append(player_name_field)
                elif isinstance(player_data, str):
                    players.append(player_data)
            
            # Create processed match
            processed_match = {
                "match_id": match_id,
                "player_id": player_id,
                "player_name": player_name,
                "match_date": match_date,
                "match_type": match_type,
                "match_result": match_result,
                "map_name": map_name,
                "players": players,
                "is_simulated": False,
                "is_scraped_with_playwright": True,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return processed_match
        except Exception as e:
            print(f"Error processing match data: {str(e)}")
            return None
    
    def save_matches_to_db(self, matches):
        """Save matches to the database"""
        for match in matches:
            # Check if the match already exists
            if not self.matches_collection.find_one({"match_id": match["match_id"]}):
                self.matches_collection.insert_one(match)
                print(f"New match saved: {match['match_id']}")
    
    def find_custom_games_between_players(self):
        """Find custom games between registered players"""
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
            "match_type": {"$regex": "Custom", "$options": "i"},
            "is_simulated": False
        }).sort("scraped_at", pymongo.DESCENDING).limit(50)
        
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
                    "is_simulated": False,
                    "is_scraped_with_playwright": True
                }
                
                # Save to database if it doesn't exist
                if not self.custom_games_collection.find_one({"match_id": match_id}):
                    self.custom_games_collection.insert_one(custom_game)
                    print(f"New custom game found: {match_id}")
                    custom_games.append(custom_game)
                
                processed_match_ids.add(match_id)
        
        return custom_games
    
    async def analyze_all_players(self):
        """Analyze all players in the database"""
        players = self.get_players_to_analyze()
        
        if not players:
            print("No players in the database to analyze")
            return
        
        for player in players:
            player_id = player["player_id"]
            player_name = player["player_name"]
            
            # Scrape matches for this player
            matches = await self.scrape_player_matches(player_id, player_name)
            
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
            
            # Wait a bit between requests to avoid overloading the server
            await asyncio.sleep(2)
        
        # Find custom games between players
        self.find_custom_games_between_players()

async def main():
    scraper = PlaywrightScraper()
    
    try:
        # Analyze all players
        await scraper.analyze_all_players()
    except Exception as e:
        print(f"Error in main loop: {str(e)}")

# For testing a specific player
async def test_specific_player(player_id, player_name):
    scraper = PlaywrightScraper()
    
    try:
        # Scrape matches for the specific player
        matches = await scraper.scrape_player_matches(player_id, player_name)
        
        # Print the results
        print(f"Found {len(matches)} matches for {player_name}")
        
        for i, match in enumerate(matches):
            print(f"\nMatch {i+1}:")
            print(f"ID: {match['match_id']}")
            print(f"Date: {match['match_date']}")
            print(f"Type: {match['match_type']}")
            print(f"Result: {match['match_result']}")
            print(f"Map: {match['map_name']}")
            print(f"Players: {', '.join(match['players'])}")
        
        # Save matches to the database
        scraper.save_matches_to_db(matches)
        
        return matches
    except Exception as e:
        print(f"Error testing specific player: {str(e)}")
        return []

if __name__ == "__main__":
    # For testing a specific player
    asyncio.run(test_specific_player("73550", "seju-fuminguez"))
    
    # For analyzing all players
    # asyncio.run(main()) 