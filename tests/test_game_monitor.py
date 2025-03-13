import pytest
import mongomock
import os
from datetime import datetime
from sejusaas.services import GameMonitorService

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

@pytest.fixture
def mock_service():
    """Create a mock service with mongomock database"""
    client = mongomock.MongoClient()
    service = GameMonitorService(client)
    
    # Add sample players to the database
    for player in SAMPLE_PLAYERS:
        service.players_collection.insert_one({
            **player,
            "added_at": datetime.now()
        })
    
    return service

def test_get_players_to_analyze(mock_service):
    """Test getting players to analyze"""
    players = mock_service.get_players_to_analyze()
    assert len(players) == min(len(SAMPLE_PLAYERS), 5)  # Should respect BATCH_SIZE
    assert all(p["player_id"] in [sp["player_id"] for sp in SAMPLE_PLAYERS] for p in players)

def test_generate_unique_match_id(mock_service):
    """Test generating unique match IDs"""
    # Same match should generate same ID
    id1 = mock_service.generate_unique_match_id(SAMPLE_CUSTOM_MATCH)
    id2 = mock_service.generate_unique_match_id(SAMPLE_CUSTOM_MATCH)
    assert id1 == id2
    
    # Different matches should generate different IDs
    id3 = mock_service.generate_unique_match_id(SAMPLE_AUTO_MATCH)
    assert id1 != id3

def test_is_custom_game_between_players(mock_service):
    """Test identifying custom games between registered players"""
    # Should identify custom game with all registered players
    assert mock_service.is_custom_game_between_players(SAMPLE_CUSTOM_MATCH, SAMPLE_PLAYERS)
    
    # Should reject auto match
    assert not mock_service.is_custom_game_between_players(SAMPLE_AUTO_MATCH, SAMPLE_PLAYERS)

def test_is_auto_match_with_registered_player(mock_service):
    """Test identifying auto matches with registered players"""
    # Should identify auto match with one registered player
    assert mock_service.is_auto_match_with_registered_player(SAMPLE_AUTO_MATCH, SAMPLE_PLAYERS)
    
    # Should reject custom game
    assert not mock_service.is_auto_match_with_registered_player(SAMPLE_CUSTOM_MATCH, SAMPLE_PLAYERS)

def test_process_matches(mock_service):
    """Test processing and storing matches"""
    matches = [SAMPLE_CUSTOM_MATCH, SAMPLE_AUTO_MATCH]
    new_custom_games, new_auto_matches = mock_service.process_matches(matches, SAMPLE_PLAYERS)
    
    assert new_custom_games == 1
    assert new_auto_matches == 1
    
    # Check that matches were stored in correct collections
    custom_games = list(mock_service.custom_games_collection.find())
    auto_matches = list(mock_service.auto_matches_collection.find())
    
    assert len(custom_games) == 1
    assert len(auto_matches) == 1
    
    # Check that matches have unique IDs and discovery time
    assert all("unique_match_id" in game for game in custom_games + auto_matches)
    assert all("discovered_at" in game for game in custom_games + auto_matches)

def test_duplicate_match_prevention(mock_service):
    """Test that duplicate matches are not stored"""
    # Process matches first time
    matches = [SAMPLE_CUSTOM_MATCH, SAMPLE_AUTO_MATCH]
    new_custom_games1, new_auto_matches1 = mock_service.process_matches(matches, SAMPLE_PLAYERS)
    
    # Process same matches again
    new_custom_games2, new_auto_matches2 = mock_service.process_matches(matches, SAMPLE_PLAYERS)
    
    # First time should store matches
    assert new_custom_games1 == 1
    assert new_auto_matches1 == 1
    
    # Second time should not store duplicates
    assert new_custom_games2 == 0
    assert new_auto_matches2 == 0 