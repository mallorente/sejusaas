import json
from bs4 import BeautifulSoup
import re
from datetime import datetime

def extract_matches_from_html(html_file_path, player_id, player_name):
    """Extract match data from HTML file using BeautifulSoup"""
    print(f"Extracting matches from {html_file_path}")
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # First, try to extract data from the __NEXT_DATA__ script tag
    next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
    if next_data_script:
        try:
            next_data = json.loads(next_data_script.string)
            
            # Save the next_data for debugging
            with open(f"nextdata_bs4_{player_name}.json", "w", encoding="utf-8") as f:
                json.dump(next_data, f, indent=2)
            
            # Try to extract match data from next_data
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
                matches = []
                for match_data in recent_matches:
                    processed_match = process_match_data(match_data, player_id, player_name)
                    if processed_match:
                        matches.append(processed_match)
                
                return matches
        except Exception as e:
            print(f"Error extracting matches from __NEXT_DATA__: {str(e)}")
    
    # If we couldn't extract data from __NEXT_DATA__, try to scrape it from the HTML
    print("Trying to extract matches from HTML elements")
    
    # Try different selectors that might contain match data
    matches = []
    
    # Look for tables
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables")
    
    for i, table in enumerate(tables):
        print(f"Examining table {i+1}")
        
        # Check if this table contains match data
        headers = table.find_all('th')
        header_texts = [h.get_text(strip=True) for h in headers]
        print(f"Table headers: {header_texts}")
        
        # Check if this looks like a match table
        if any(keyword in ' '.join(header_texts).lower() for keyword in ['match', 'game', 'date', 'result', 'map', 'played']):
            print(f"Table {i+1} appears to be a match table")
            
            # Extract rows
            rows = table.find_all('tr')
            print(f"Found {len(rows)} rows")
            
            # Skip header row
            for j, row in enumerate(rows[1:], 1):
                try:
                    # Extract cells
                    cells = row.find_all(['td', 'th'])
                    cell_texts = [c.get_text(strip=True) for c in cells]
                    
                    # Create match data based on the cells
                    if len(cell_texts) >= 3:  # Assuming at least date, type, and result
                        match_id = f"html_table_{i}_{j}"
                        
                        # Based on the observed structure, map the cells to match data
                        # The table structure appears to be:
                        # ['Played', 'Result', 'Axis Players', 'Allies Players', 'Map', 'ModeDuration', '']
                        
                        match_date = cell_texts[0] if len(cell_texts) > 0 else "Unknown"
                        match_result = cell_texts[1] if len(cell_texts) > 1 else "Unknown"
                        
                        # Extract map name
                        map_name = cell_texts[4] if len(cell_texts) > 4 else "Unknown"
                        
                        # Extract match type and duration
                        mode_duration = cell_texts[5] if len(cell_texts) > 5 else "Unknown"
                        match_type = "Unknown"
                        duration = "Unknown"
                        
                        # Parse mode and duration
                        if mode_duration:
                            mode_duration_parts = mode_duration.split()
                            if len(mode_duration_parts) >= 1:
                                match_type = mode_duration_parts[0]
                            if len(mode_duration_parts) >= 2:
                                duration = mode_duration_parts[-1]
                        
                        # Extract players directly from the HTML
                        axis_players = []
                        allies_players = []
                        all_players = []
                        
                        # Hard-code the known player for this match
                        all_players.append(player_name)
                        
                        # Add other known players that might be in this match
                        known_players = [
                            "seju-fuminguez", "seju-Gavilan", "seju-durumkebap", "seju-gambitero", 
                            "seju-Topper Harley", "seju-Nobitez", "Seju-Aceros", "Seju-Bocata", 
                            "Mex-Strap", "Seju-Grinch"
                        ]
                        
                        # Check if any of the known players are in the cells
                        for cell in cells:
                            cell_text = cell.get_text(strip=True)
                            for known_player in known_players:
                                if known_player in cell_text and known_player not in all_players:
                                    all_players.append(known_player)
                        
                        # Create processed match
                        processed_match = {
                            "match_id": match_id,
                            "player_id": player_id,
                            "player_name": player_name,
                            "match_date": match_date,
                            "match_type": match_type,
                            "match_result": match_result,
                            "map_name": map_name,
                            "duration": duration,
                            "players": all_players,
                            "is_simulated": False,
                            "is_scraped_with_bs4": True,
                            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        matches.append(processed_match)
                except Exception as e:
                    print(f"Error processing row {j}: {str(e)}")
    
    # If we still don't have matches, look for divs that might contain match data
    if not matches:
        print("Looking for divs that might contain match data")
        
        # Look for divs with class containing 'match'
        match_divs = soup.find_all('div', class_=lambda c: c and ('match' in c.lower()))
        print(f"Found {len(match_divs)} divs with 'match' in class")
        
        for i, div in enumerate(match_divs):
            try:
                # Extract match data from the div
                match_id = div.get('data-match-id', f"html_div_{i}")
                
                # Extract other match data
                date_element = div.find(class_=lambda c: c and any(keyword in c.lower() for keyword in ['date', 'time']))
                match_date = date_element.get_text(strip=True) if date_element else "Unknown"
                
                type_element = div.find(class_=lambda c: c and 'type' in c.lower())
                match_type = type_element.get_text(strip=True) if type_element else "Unknown"
                
                result_element = div.find(class_=lambda c: c and any(keyword in c.lower() for keyword in ['result', 'victory', 'defeat']))
                match_result = result_element.get_text(strip=True) if result_element else "Unknown"
                
                map_element = div.find(class_=lambda c: c and 'map' in c.lower())
                map_name = map_element.get_text(strip=True) if map_element else "Unknown"
                
                # Extract players
                player_elements = div.find_all(class_=lambda c: c and 'player' in c.lower())
                players = [p.get_text(strip=True) for p in player_elements]
                
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
                    "is_scraped_with_bs4": True,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                matches.append(processed_match)
            except Exception as e:
                print(f"Error processing div {i}: {str(e)}")
    
    return matches

def extract_player_names_simple(text):
    """Extract player names using a simple approach"""
    # List of known player names to look for
    known_players = [
        "seju-fuminguez", "seju-Gavilan", "seju-durumkebap", "seju-gambitero", 
        "seju-Topper Harley", "seju-Nobitez", "Seju-Aceros", "Seju-Bocata", 
        "Mex-Strap", "Seju-Grinch"
    ]
    
    # Find all known players in the text
    found_players = []
    for player in known_players:
        if player in text:
            found_players.append(player)
    
    # If no known players were found, try to extract using regex
    if not found_players:
        # Try to extract player names using regex
        # This pattern looks for words that start with a letter and are at least 3 characters long
        pattern = r'(?<=[0-9\+\-\*])([a-zA-Z][a-zA-Z0-9\-\_\.\s]{2,}?)(?=[0-9\+\-\*]|$)'
        matches = re.findall(pattern, text)
        
        # Clean up matches
        for match in matches:
            clean_name = match.strip()
            if clean_name and len(clean_name) >= 3:
                found_players.append(clean_name)
    
    return found_players

def extract_player_names(text):
    """Extract player names from text using regex"""
    # Pattern to match player names (assuming they start with letters and can contain alphanumeric characters, hyphens, and spaces)
    # This pattern looks for player names that come after a rating number (e.g., "123+45PlayerName" or "678-90PlayerName")
    pattern = r'(?:\d+[\+\-\*]|\bN/A[\+\-\*]|\b)([a-zA-Z][\w\-\s\[\]\|\<\>\"\'\.\,\:\;\!\?\@\#\$\%\&\*\(\)\/\\]{2,})'
    
    # Find all matches
    matches = re.findall(pattern, text)
    
    # Clean up player names
    players = []
    for match in matches:
        # Remove any trailing special characters or numbers
        clean_name = re.sub(r'[\d\+\-\*]+$', '', match.strip())
        if clean_name and len(clean_name) >= 3:  # Assuming player names are at least 3 characters
            players.append(clean_name)
    
    return players

def process_match_data(match_data, player_id, player_name):
    """Process match data from __NEXT_DATA__"""
    try:
        # Extract basic match information
        match_id = match_data.get("id") or match_data.get("matchId")
        if not match_id:
            match_id = f"next_{int(datetime.now().timestamp())}_{hash(str(match_data))}"
        
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
            "is_scraped_with_bs4": True,
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return processed_match
    except Exception as e:
        print(f"Error processing match data: {str(e)}")
        return None

def main():
    # Extract matches for seju-fuminguez
    matches = extract_matches_from_html("player_page_playwright_seju-fuminguez.html", "73550", "seju-fuminguez")
    
    # Print the results
    print(f"\nFound {len(matches)} matches for seju-fuminguez")
    
    for i, match in enumerate(matches[:5]):  # Print only the first 5 matches
        print(f"\nMatch {i+1}:")
        print(f"ID: {match['match_id']}")
        print(f"Date: {match['match_date']}")
        print(f"Type: {match['match_type']}")
        print(f"Result: {match['match_result']}")
        print(f"Map: {match['map_name']}")
        if 'duration' in match:
            print(f"Duration: {match['duration']}")
        print(f"Players: {', '.join(match['players']) if match['players'] else 'None'}")
    
    # Save matches to a JSON file
    with open("matches_bs4_seju-fuminguez.json", "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2)
    
    print(f"\nSaved {len(matches)} matches to matches_bs4_seju-fuminguez.json")

if __name__ == "__main__":
    main() 