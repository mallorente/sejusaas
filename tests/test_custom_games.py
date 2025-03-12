import pytest
import mongomock
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import os
import time

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import COH3StatsAnalyzer

# Sample test data
SAMPLE_PLAYERS = [
    {"player_id": "123", "player_name": "seju-fuminguez"},
    {"player_id": "456", "player_name": "seju-Gavilan"},
    {"player_id": "789", "player_name": "seju-durumkebap"},
    {"player_id": "101", "player_name": "seju-player4"},
    {"player_id": "102", "player_name": "seju-player5"},
    {"player_id": "103", "player_name": "seju-player6"},
    {"player_id": "104", "player_name": "seju-player7"},
    {"player_id": "105", "player_name": "seju-player8"},
    {"player_id": "106", "player_name": "seju-player9"},
    {"player_id": "107", "player_name": "seju-player10"}  # Testing with 10 players
]

SAMPLE_CUSTOM_MATCH = {
    "match_id": "custom_1",
    "match_date": "2024-03-09T15:30:00",
    "match_type": "Custom Game",
    "match_result": "Victory",
    "map_name": "Fields of Normandy",
    "axis_players": [
        {"player_id": "123", "player_name": "seju-fuminguez"},
        {"player_id": "456", "player_name": "seju-Gavilan"}
    ],
    "allies_players": [
        {"player_id": "789", "player_name": "seju-durumkebap"}
    ]
}

SAMPLE_RANKED_MATCH = {
    "match_id": "ranked_1",
    "match_date": "2024-03-09T15:30:00",
    "match_type": "Ranked 1v1",
    "match_result": "Victory",
    "map_name": "Fields of Normandy",
    "axis_players": [
        {"player_id": "123", "player_name": "seju-fuminguez"}
    ],
    "allies_players": [
        {"player_id": "456", "player_name": "seju-Gavilan"}
    ]
}

SAMPLE_MIXED_MATCH = {
    "match_id": "custom_2",
    "match_date": "2024-03-09T15:30:00",
    "match_type": "Custom Game",
    "match_result": "Victory",
    "map_name": "Fields of Normandy",
    "axis_players": [
        {"player_id": "123", "player_name": "seju-fuminguez"},
        {"player_id": "999", "player_name": "unknown-player"}
    ],
    "allies_players": [
        {"player_id": "456", "player_name": "seju-Gavilan"}
    ]
}

@pytest.fixture
def mock_analyzer():
    """Create a mock analyzer with mongomock database"""
    with patch('pymongo.MongoClient', mongomock.MongoClient):
        analyzer = COH3StatsAnalyzer()
        
        # Add sample players to the database
        for player in SAMPLE_PLAYERS:
            analyzer.add_player(player["player_id"], player["player_name"])
        
        yield analyzer

@pytest.fixture
def mock_match_fetcher():
    """Create a mock match fetcher"""
    mock = MagicMock()
    mock.fetch_matches_for_player.return_value = [
        SAMPLE_CUSTOM_MATCH,
        SAMPLE_RANKED_MATCH,
        SAMPLE_MIXED_MATCH
    ]
    return mock

def test_is_custom_game_between_players(mock_analyzer):
    """Test the custom game detection logic"""
    # Test with a valid custom game between registered players
    assert mock_analyzer.is_custom_game_between_players(SAMPLE_CUSTOM_MATCH, SAMPLE_PLAYERS) == True
    
    # Test with a ranked game (not custom)
    assert mock_analyzer.is_custom_game_between_players(SAMPLE_RANKED_MATCH, SAMPLE_PLAYERS) == False
    
    # Test with a custom game including non-registered players
    assert mock_analyzer.is_custom_game_between_players(SAMPLE_MIXED_MATCH, SAMPLE_PLAYERS) == False

def test_generate_unique_match_id(mock_analyzer):
    """Test unique match ID generation"""
    # Generate ID for the same match twice
    id1 = mock_analyzer.generate_unique_match_id(SAMPLE_CUSTOM_MATCH)
    id2 = mock_analyzer.generate_unique_match_id(SAMPLE_CUSTOM_MATCH)
    
    # Should generate the same ID for the same match
    assert id1 == id2
    
    # Should generate different IDs for different matches
    id3 = mock_analyzer.generate_unique_match_id(SAMPLE_RANKED_MATCH)
    assert id1 != id3

def test_check_for_new_games(mock_analyzer, mock_match_fetcher):
    """Test the new game checking functionality"""
    # Replace the real match fetcher with our mock
    mock_analyzer.real_match_fetcher = mock_match_fetcher
    
    # First check should find one new custom game
    mock_analyzer.check_for_new_games()
    games = mock_analyzer.get_custom_games()
    assert len(games) == 1
    assert games[0]['match_type'] == "Custom Game"
    
    # Second check should not find any new games (same data)
    mock_analyzer.check_for_new_games()
    games = mock_analyzer.get_custom_games()
    assert len(games) == 1  # Still only one game

def test_duplicate_game_prevention(mock_analyzer):
    """Test that the same game is not stored twice"""
    # Create two copies of the same game with different player order
    game1 = SAMPLE_CUSTOM_MATCH.copy()
    game2 = SAMPLE_CUSTOM_MATCH.copy()
    game2['axis_players'] = game1['axis_players'][::-1]  # Reverse player order
    
    # Generate IDs for both games
    id1 = mock_analyzer.generate_unique_match_id(game1)
    id2 = mock_analyzer.generate_unique_match_id(game2)
    
    # Should generate the same ID despite different player order
    assert id1 == id2

def test_custom_games_collection(mock_analyzer):
    """Test the custom games collection operations"""
    # Add a custom game
    game = SAMPLE_CUSTOM_MATCH.copy()
    game['unique_match_id'] = mock_analyzer.generate_unique_match_id(game)
    game['discovered_at'] = datetime.now()
    mock_analyzer.custom_games_collection.insert_one(game)
    
    # Try to add the same game again (should be prevented by unique ID)
    mock_analyzer.custom_games_collection.update_one(
        {"unique_match_id": game['unique_match_id']},
        {"$set": game},
        upsert=True
    )
    
    # Should still only have one game
    games = mock_analyzer.get_custom_games()
    assert len(games) == 1

def test_execution_time(mock_analyzer, mock_match_fetcher):
    """Test the execution time of a complete check cycle"""
    # Replace the real match fetcher with our mock
    mock_analyzer.real_match_fetcher = mock_match_fetcher
    
    # Simulate delay in API calls (0.5 seconds per player)
    def delayed_fetch(*args, **kwargs):
        time.sleep(0.5)  # Simulate API delay
        days_back = kwargs.get('days_back', 1)
        # Return fewer matches if checking recent history
        if days_back < 1:
            return [SAMPLE_CUSTOM_MATCH]
        return [SAMPLE_CUSTOM_MATCH, SAMPLE_RANKED_MATCH, SAMPLE_MIXED_MATCH]
    
    mock_match_fetcher.fetch_matches_for_player.side_effect = delayed_fetch
    
    # First run (should check last 24h for all players in batch)
    start_time = time.time()
    mock_analyzer.check_for_new_games()
    first_run_time = time.time() - start_time
    
    # Second run (should only check last hour for recent players)
    start_time = time.time()
    mock_analyzer.check_for_new_games()
    second_run_time = time.time() - start_time
    
    # Print execution time details
    print(f"\nPerformance Analysis:")
    print(f"First run (24h check) execution time: {first_run_time:.2f} seconds")
    print(f"Second run (1h check) execution time: {second_run_time:.2f} seconds")
    print(f"Batch size: {len(mock_analyzer.get_players_to_analyze())}")
    print(f"Average time per player (first run): {first_run_time/len(mock_analyzer.get_players_to_analyze()):.2f} seconds")
    print(f"Average time per player (second run): {second_run_time/len(mock_analyzer.get_players_to_analyze()):.2f} seconds")
    print(f"Estimated monthly Render usage:")
    executions_per_month = (30 * 24 * 60) / (15)  # 15 minute intervals
    monthly_minutes = (executions_per_month * second_run_time) / 60
    print(f"- Executions per month: {executions_per_month:.0f}")
    print(f"- Total minutes: {monthly_minutes:.1f}")
    print(f"- Percentage of free tier: {(monthly_minutes/500)*100:.1f}%")
    
    # Test assertions
    assert first_run_time > 0  # Should take some time
    assert second_run_time < first_run_time  # Second run should be faster
    assert second_run_time < 5  # Shouldn't take too long for test data 