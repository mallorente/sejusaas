#!/usr/bin/env python
"""
Script to change the log level of a running COH3 Stats Analyzer instance.
This is useful for systems that don't support signals or for remote management.

Usage:
  python change_log_level.py [debug|info|warning|error|critical]

If no level is specified, it will cycle through: INFO -> DEBUG -> WARNING -> INFO
"""

import os
import sys
import pymongo
from datetime import datetime

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://usuario:contraseña@cluster0.mongodb.net/")
DB_NAME = "coh3stats_db"
CONFIG_COLLECTION = "config"

def get_current_level():
    """Get the current log level from the database"""
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    config = db[CONFIG_COLLECTION].find_one({"key": "log_level"})
    if not config:
        # Default to INFO if not set
        return "INFO"
    return config["value"]

def set_log_level(level):
    """Set the log level in the database"""
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    # Update or insert the log level
    db[CONFIG_COLLECTION].update_one(
        {"key": "log_level"},
        {"$set": {
            "key": "log_level",
            "value": level,
            "updated_at": datetime.now()
        }},
        upsert=True
    )
    
    print(f"Log level set to: {level}")
    print("The running application will check for this change periodically.")

def cycle_log_level():
    """Cycle through log levels: INFO -> DEBUG -> WARNING -> INFO"""
    current_level = get_current_level()
    
    if current_level == "INFO":
        new_level = "DEBUG"
    elif current_level == "DEBUG":
        new_level = "WARNING"
    else:
        new_level = "INFO"
    
    set_log_level(new_level)

def main():
    """Main function"""
    if len(sys.argv) > 1:
        # Use the provided level
        level = sys.argv[1].upper()
        if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            print(f"Invalid log level: {level}")
            print("Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL")
            sys.exit(1)
        set_log_level(level)
    else:
        # Cycle through levels
        cycle_log_level()

if __name__ == "__main__":
    main() 