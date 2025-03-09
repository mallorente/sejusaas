import os
import json
import re
from bs4 import BeautifulSoup

def extract_match_data_from_table(html_file_path, player_id, player_name):
    """
    Extract match data from the HTML table in the player page
    """
    print(f"Extracting match data from {html_file_path}")
    
    if not os.path.exists(html_file_path):
        print(f"File not found: {html_file_path}")
        return []
    
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

def get_real_matches_from_html(player_id, player_name):
    """
    Get real match data by extracting it from the HTML table on the player's page
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
    matches = extract_match_data_from_table(html_file_path, player_id, player_name)
    
    # Save matches to a JSON file for reference
    output_file = f"matches_html_{player_name}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2)
    
    return matches

def find_custom_games(matches):
    """
    Find custom games among the matches
    """
    custom_games = []
    for match in matches:
        if match['match_type'] == 'Custom':
            custom_games.append(match)
    
    print(f"Found {len(custom_games)} custom games")
    
    # Save custom games to a JSON file
    output_file = "custom_games.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(custom_games, f, indent=2)
    
    return custom_games

def main():
    # Test with seju-fuminguez
    player_id = "73550"
    player_name = "seju-fuminguez"
    
    matches = get_real_matches_from_html(player_id, player_name)
    
    if matches:
        # Print first 5 matches for verification
        print("\nFirst 5 matches:")
        for i, match in enumerate(matches[:5]):
            print(f"Match {i+1}:")
            print(f"  Date: {match['match_date']}")
            print(f"  Result: {match['match_result']} ({match['rating_change']})")
            print(f"  Map: {match['map_name']}")
            print(f"  Mode: {match['match_type']} ({match['duration']})")
            print(f"  Axis Players: {len(match['axis_players'])}")
            print(f"  Allies Players: {len(match['allies_players'])}")
            print()
        
        # Find custom games
        custom_games = find_custom_games(matches)
        
        if custom_games:
            print("\nCustom games:")
            for i, match in enumerate(custom_games[:5]):
                print(f"Custom Game {i+1}:")
                print(f"  Date: {match['match_date']}")
                print(f"  Map: {match['map_name']}")
                print(f"  Duration: {match['duration']}")
                print(f"  Axis Players: {[p['player_name'] for p in match['axis_players']]}")
                print(f"  Allies Players: {[p['player_name'] for p in match['allies_players']]}")
                print()

if __name__ == "__main__":
    main() 