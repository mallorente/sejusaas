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
    {"player_id": "789", "player_name": "seju-durumkebap"}
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

SAMPLE_AUTO_MATCH = {
    "match_id": "auto_1",
    "match_date": "2024-03-09T15:30:00",
    "match_type": "Ranked 1v1",
    "match_result": "Victory",
    "map_name": "Fields of Normandy",
    "axis_players": [
        {"player_id": "123", "player_name": "seju-fuminguez"}
    ],
    "allies_players": [
        {"player_id": "999", "player_name": "random-player"}
    ]
}

SAMPLE_AUTO_MATCH_2 = {
    "match_id": "auto_2",
    "match_date": "2024-03-09T16:30:00",
    "match_type": "Ranked 2v2",
    "match_result": "Defeat",
    "map_name": "Montherme",
    "axis_players": [
        {"player_id": "123", "player_name": "seju-fuminguez"},
        {"player_id": "456", "player_name": "seju-Gavilan"}
    ],
    "allies_players": [
        {"player_id": "888", "player_name": "random-player1"},
        {"player_id": "777", "player_name": "random-player2"}
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
        SAMPLE_AUTO_MATCH,
        SAMPLE_AUTO_MATCH_2
    ]
    return mock

def test_is_auto_match_with_registered_player(mock_analyzer):
    """Test the auto match detection logic"""
    # Test with a valid auto match with a registered player
    assert mock_analyzer.is_auto_match_with_registered_player(SAMPLE_AUTO_MATCH, SAMPLE_PLAYERS) == True
    
    # Test with a custom game (should return False)
    assert mock_analyzer.is_auto_match_with_registered_player(SAMPLE_CUSTOM_MATCH, SAMPLE_PLAYERS) == False

def test_check_for_new_games_with_auto_matches(mock_analyzer, mock_match_fetcher):
    """Test the new game checking functionality with auto matches"""
    # Replace the real match fetcher with our mock
    mock_analyzer.real_match_fetcher = mock_match_fetcher
    
    # First check should find one custom game and two auto matches
    mock_analyzer.check_for_new_games()
    
    # Check custom games
    custom_games = mock_analyzer.get_custom_games()
    assert len(custom_games) == 1
    assert custom_games[0]['match_type'] == "Custom Game"
    
    # Check auto matches
    auto_matches = mock_analyzer.get_auto_matches()
    assert len(auto_matches) == 2
    
    # Verify the auto matches have the correct match types
    match_types = [match['match_type'] for match in auto_matches]
    assert "Ranked 1v1" in match_types
    assert "Ranked 2v2" in match_types
    
    # Second check should not find any new games (same data)
    mock_analyzer.check_for_new_games()
    
    # Should still have the same number of games
    assert len(mock_analyzer.get_custom_games()) == 1
    assert len(mock_analyzer.get_auto_matches()) == 2

def test_auto_matches_collection(mock_analyzer):
    """Test the auto matches collection operations"""
    # Add an auto match
    match = SAMPLE_AUTO_MATCH.copy()
    match['unique_match_id'] = mock_analyzer.generate_unique_match_id(match)
    match['discovered_at'] = datetime.now()
    mock_analyzer.auto_matches_collection.insert_one(match)
    
    # Try to add the same match again (should be prevented by unique ID)
    mock_analyzer.auto_matches_collection.update_one(
        {"unique_match_id": match['unique_match_id']},
        {"$set": match},
        upsert=True
    )
    
    # Should still only have one match
    auto_matches = mock_analyzer.get_auto_matches()
    assert len(auto_matches) == 1
    assert auto_matches[0]['match_type'] == "Ranked 1v1" 