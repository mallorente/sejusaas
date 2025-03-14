#!/usr/bin/env python3
"""
Export existing custom games from the database to Google Sheets.
This script will connect to the MongoDB database, retrieve all custom games,
and export them to the configured Google Sheet.
"""

import os
import sys
import logging
import argparse
import pymongo
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('export_custom_games')

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the SheetsExporter
try:
    from sejusaas.services.sheets_exporter import SheetsExporter
except ImportError:
    logger.error("Could not import SheetsExporter. Make sure you're running this script from the project root.")
    sys.exit(1)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Export custom games to Google Sheets')
    parser.add_argument('--limit', type=int, default=0, help='Limit the number of games to export (0 for all)')
    parser.add_argument('--force', action='store_true', help='Force export even if games are already in the sheet')
    return parser.parse_args()

def main():
    """Main function to export custom games to Google Sheets"""
    # Parse command line arguments
    args = parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Check if service account file exists
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if service_account_file and not os.path.exists(service_account_file):
        logger.error(f"Service account file not found: {service_account_file}")
        logger.info("Please make sure the service account file exists or set GOOGLE_SERVICE_ACCOUNT_JSON")
        sys.exit(1)
    
    # Get MongoDB connection string
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        logger.error("MONGO_URI environment variable not set")
        sys.exit(1)
    
    # Connect to MongoDB
    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client["coh3stats_db"]
        custom_games_collection = db["custom_games"]
        logger.info("Connected to MongoDB")
    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        sys.exit(1)
    
    # Initialize the SheetsExporter
    logger.info("Initializing SheetsExporter...")
    exporter = SheetsExporter()
    
    # Check if connected
    if not exporter.is_connected():
        logger.error("SheetsExporter is not connected. Check your credentials and permissions.")
        sys.exit(1)
    
    logger.info("SheetsExporter initialized successfully!")
    
    # Get existing match IDs from the sheet
    existing_match_ids = exporter._get_existing_match_ids() if not args.force else []
    logger.info(f"Found {len(existing_match_ids)} existing matches in the sheet")
    
    # Query custom games from the database
    query = {}
    if not args.force and existing_match_ids:
        query = {"unique_match_id": {"$nin": existing_match_ids}}
    
    # Apply limit if specified
    cursor = custom_games_collection.find(query)
    if args.limit > 0:
        cursor = cursor.limit(args.limit)
    
    # Convert cursor to list
    custom_games = list(cursor)
    logger.info(f"Found {len(custom_games)} custom games to export")
    
    if not custom_games:
        logger.info("No new custom games to export")
        return
    
    # Export custom games to Google Sheets
    try:
        exported_count = exporter.export_matches(custom_games)
        logger.info(f"Successfully exported {exported_count} custom games to Google Sheets!")
    except Exception as e:
        logger.error(f"Error exporting custom games to Google Sheets: {str(e)}")
        sys.exit(1)
    
    logger.info("Export completed successfully!")

if __name__ == "__main__":
    main() 