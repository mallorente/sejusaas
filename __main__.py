"""Main entry point for the SEJU Stats Service"""

import os
import logging
from dotenv import load_dotenv
from sejusaas.services import GameMonitorService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('logs', 'sejusaas.log'))
    ]
)

def main():
    """Main entry point"""
    service = GameMonitorService()
    service.run()

if __name__ == "__main__":
    main() 