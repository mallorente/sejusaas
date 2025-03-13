import os
import sys
import logging
import pymongo
from dotenv import load_dotenv
from services import GameMonitorService

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('logs', 'sejusaas.log'))
    ]
)
logger = logging.getLogger('sejusaas')

def main():
    """Main entry point for the service"""
    # Load environment variables
    load_dotenv()
    
    # Get MongoDB connection string
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        logger.error("MONGO_URI environment variable not set")
        sys.exit(1)
    
    try:
        # Connect to MongoDB
        client = pymongo.MongoClient(mongo_uri)
        
        # Create and run the game monitor service
        service = GameMonitorService(client)
        service.run()
        
    except pymongo.errors.ConnectionError as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    main() 