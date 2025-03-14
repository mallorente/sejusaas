#!/usr/bin/env python3
"""
Test script for Google Sheets integration.
This script will test the connection to Google Sheets and export a sample match.
"""

import os
import sys
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_sheets_export')

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the SheetsExporter
try:
    from sejusaas.services.sheets_exporter import SheetsExporter
except ImportError:
    logger.error("Could not import SheetsExporter. Make sure you're running this script from the project root.")
    sys.exit(1)

def create_sample_match():
    """Create a sample match for testing"""
    return {
        "match_id": "test_match_1",
        "unique_match_id": f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "player_id": "12345",
        "player_name": "test_player",
        "match_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "match_type": "custom",
        "match_result": "axis victory",
        "map_name": "Test Map",
        "axis_players": [
            {"player_id": "12345", "player_name": "test_player"},
            {"player_id": "67890", "player_name": "test_player2"}
        ],
        "allies_players": [
            {"player_id": "54321", "player_name": "test_player3"},
            {"player_id": "09876", "player_name": "test_player4"}
        ],
        "is_simulated": False,
        "is_scraped": True,
        "scraped_at": datetime.now().isoformat(),
        "discovered_at": datetime.now()
    }

def main():
    """Main function to test Google Sheets integration"""
    # Load environment variables
    load_dotenv()
    
    # Check if service account file exists
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if service_account_file and not os.path.exists(service_account_file):
        logger.error(f"Service account file not found: {service_account_file}")
        logger.info("Please make sure the service account file exists or set GOOGLE_SERVICE_ACCOUNT_JSON")
        sys.exit(1)
    
    # Initialize the SheetsExporter
    logger.info("Initializing SheetsExporter...")
    exporter = SheetsExporter()
    
    # Check if connected
    if not exporter.is_connected():
        logger.error("SheetsExporter is not connected. Check your credentials and permissions.")
        sys.exit(1)
    
    logger.info("SheetsExporter initialized successfully!")
    
    # Create a sample match
    logger.info("Creating sample match...")
    sample_match = create_sample_match()
    
    # Export the sample match
    logger.info("Exporting sample match to Google Sheets...")
    try:
        exported_count = exporter.export_matches([sample_match])
        if exported_count > 0:
            logger.info(f"Successfully exported {exported_count} match to Google Sheets!")
        else:
            logger.warning("No matches were exported. The match might already exist in the sheet.")
    except Exception as e:
        logger.error(f"Error exporting match to Google Sheets: {str(e)}")
        sys.exit(1)
    
    logger.info("Test completed successfully!")

if __name__ == "__main__":
    main() 