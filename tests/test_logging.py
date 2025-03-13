import pytest
import mongomock
import os
import sys
import logging
from unittest.mock import patch, MagicMock, call
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main

@pytest.fixture
def mock_logger():
    """Create a mock logger for testing"""
    logger = MagicMock()
    return logger

@pytest.fixture
def mock_analyzer():
    """Create a mock analyzer with mongomock database"""
    with patch('pymongo.MongoClient', mongomock.MongoClient):
        # Patch the logger
        with patch('main.logger') as mock_logger:
            analyzer = main.COH3StatsAnalyzer()
            
            # Add a test player
            analyzer.add_player("123", "test-player")
            
            yield analyzer, mock_logger

def test_log_level_change_via_signal():
    """Test changing log level via signal handler"""
    # Save original logger and level
    original_logger = main.logger
    original_level = main.logger.level
    
    try:
        # Call the signal handler
        main.change_log_level(None, None)
        
        # Check that level changed to DEBUG
        assert main.current_log_level == 'DEBUG'
        assert main.logger.level == logging.DEBUG
        
        # Call again to change to WARNING
        main.change_log_level(None, None)
        assert main.current_log_level == 'WARNING'
        assert main.logger.level == logging.WARNING
        
        # Call again to change back to INFO
        main.change_log_level(None, None)
        assert main.current_log_level == 'INFO'
        assert main.logger.level == logging.INFO
    finally:
        # Restore original logger and level
        main.logger = original_logger
        main.logger.setLevel(original_level)

def test_log_level_change_via_database(mock_analyzer):
    """Test changing log level via database"""
    analyzer, mock_logger = mock_analyzer
    
    # Set up a log level in the database
    analyzer.config_collection.insert_one({
        "key": "log_level",
        "value": "DEBUG",
        "updated_at": datetime.now()
    })
    
    # Force last check time to be old
    analyzer.last_log_check = datetime.now().replace(year=2000)
    
    # Check log level
    analyzer.check_log_level()
    
    # Verify that logger.setLevel was called with DEBUG
    mock_logger.info.assert_any_call("Changing log level from INFO to DEBUG (from database)")
    
    # Change to WARNING
    analyzer.config_collection.update_one(
        {"key": "log_level"},
        {"$set": {"value": "WARNING"}}
    )
    
    # Force last check time to be old
    analyzer.last_log_check = datetime.now().replace(year=2000)
    
    # Check log level again
    analyzer.check_log_level()
    
    # Verify that logger.setLevel was called with WARNING
    mock_logger.info.assert_any_call("Changing log level from DEBUG to WARNING (from database)")

def test_logging_during_game_check(mock_analyzer):
    """Test that appropriate log messages are generated during game check"""
    analyzer, mock_logger = mock_analyzer
    
    # Create a mock match fetcher
    mock_match_fetcher = MagicMock()
    mock_match_fetcher.fetch_matches_for_player.return_value = [{
        "match_id": "test_match",
        "match_date": "2024-03-09T15:30:00",
        "match_type": "Custom Game",
        "match_result": "Victory",
        "map_name": "Fields of Normandy",
        "axis_players": [
            {"player_id": "123", "player_name": "test-player"}
        ],
        "allies_players": [
            {"player_id": "123", "player_name": "test-player"}
        ]
    }]
    
    # Replace the real match fetcher with our mock
    analyzer.real_match_fetcher = mock_match_fetcher
    
    # Run the check
    analyzer.check_for_new_games()
    
    # Verify that appropriate log messages were generated
    # Check for the start message (without checking the exact datetime)
    start_calls = [call for call in mock_logger.info.call_args_list if "Starting check for new games" in str(call)]
    assert len(start_calls) > 0
    
    # Check for the summary message
    mock_logger.info.assert_any_call("Found 1 new custom games and 0 new auto matches in this batch")
    
    # Check for debug logs about match details
    debug_calls = [call for call in mock_logger.debug.call_args_list if "Custom game details" in str(call)]
    assert len(debug_calls) > 0

def test_file_logging():
    """Test that file logging works"""
    # Create a temporary log directory
    temp_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_logs')
    if not os.path.exists(temp_log_dir):
        os.makedirs(temp_log_dir)
    
    # Create a test logger with file handler
    test_logger = logging.getLogger('test_logger')
    test_logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    test_logger.handlers = []
    
    # Add a file handler
    log_file = os.path.join(temp_log_dir, 'test.log')
    file_handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    test_logger.addHandler(file_handler)
    
    # Log some messages
    test_logger.debug("Debug message")
    test_logger.info("Info message")
    test_logger.warning("Warning message")
    
    # Close the handler
    file_handler.close()
    
    # Check that the log file exists and contains the messages
    assert os.path.exists(log_file)
    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "Debug message" in log_content
        assert "Info message" in log_content
        assert "Warning message" in log_content
    
    # Clean up
    os.remove(log_file)
    os.rmdir(temp_log_dir) 