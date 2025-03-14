import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound

# Configure logging
logger = logging.getLogger('sheets_exporter')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Constants
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
DEFAULT_SPREADSHEET_ID = "1JHrIoReIXPsYJdfbcFdq1csHEH8HsoJkhin3wF5NkOs"
DEFAULT_WORKSHEET_NAME = "Auto Registro"

class SheetsExporter:
    def __init__(self, service_account_file: str = None):
        """Initialize the Google Sheets exporter"""
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        self.service_account_file = service_account_file or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        self.spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID", DEFAULT_SPREADSHEET_ID)
        self.worksheet_name = os.getenv("GOOGLE_SHEETS_WORKSHEET", DEFAULT_WORKSHEET_NAME)
        
        if not self.service_account_file and not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
            logger.warning("No service account file or JSON specified. Google Sheets export disabled.")
            return
            
        try:
            self._initialize_client()
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {str(e)}")
    
    def _initialize_client(self):
        """Initialize the Google Sheets client"""
        try:
            # Check if service account info is provided as a JSON string in environment variable
            if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
                service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
                credentials = Credentials.from_service_account_info(
                    service_account_info, scopes=SCOPES
                )
            else:
                # Otherwise, load from file
                credentials = Credentials.from_service_account_file(
                    self.service_account_file, scopes=SCOPES
                )
                
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            # Try to open the worksheet, create it if it doesn't exist
            try:
                self.worksheet = self.spreadsheet.worksheet(self.worksheet_name)
                logger.info(f"Connected to worksheet: {self.worksheet_name}")
            except gspread.exceptions.WorksheetNotFound:
                logger.info(f"Worksheet {self.worksheet_name} not found, creating it...")
                self.worksheet = self.spreadsheet.add_worksheet(
                    title=self.worksheet_name, rows=1000, cols=20
                )
                # Initialize the header row
                self._initialize_header_row()
                
        except Exception as e:
            logger.error(f"Error initializing Google Sheets client: {str(e)}")
            raise
    
    def _initialize_header_row(self):
        """Initialize the header row in the worksheet"""
        headers = [
            "Fecha", "Hora", "Mapa", "Ejército Eje", "Ejército Aliados", 
            "Jugador Eje 1", "Jugador Eje 2", "Jugador Eje 3", "Jugador Eje 4",
            "Jugador Aliados 1", "Jugador Aliados 2", "Jugador Aliados 3", "Jugador Aliados 4",
            "Puntos Eje", "Puntos Aliados", "Match ID", "Exportado"
        ]
        self.worksheet.update([headers])
        self.worksheet.format('A1:Q1', {'textFormat': {'bold': True}})
    
    def is_connected(self) -> bool:
        """Check if the client is connected to Google Sheets"""
        return self.client is not None and self.worksheet is not None
    
    def _format_match_for_sheet(self, match: Dict[str, Any]) -> List[str]:
        """Format a match for the Google Sheet"""
        # Extract date and time from match_date
        match_date = match.get('match_date', '')
        date_str = ""
        time_str = ""
        
        try:
            if match_date:
                # Try different date formats
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        dt = datetime.strptime(match_date, fmt)
                        date_str = dt.strftime("%d/%m/%Y")
                        time_str = dt.strftime("%H:%M")
                        break
                    except ValueError:
                        continue
        except Exception as e:
            logger.warning(f"Error parsing date {match_date}: {str(e)}")
            # If parsing fails, use the original string
            date_parts = match_date.split()
            if len(date_parts) >= 1:
                date_str = date_parts[0]
            if len(date_parts) >= 2:
                time_str = date_parts[1]
        
        # Determine winner and assign points
        match_result = match.get('match_result', '').lower()
        axis_points = "500" if "axis" in match_result and "victory" in match_result else "0"
        allies_points = "500" if "allies" in match_result and "victory" in match_result else "0"
        
        # If neither explicitly won, check if we can determine from other fields
        if axis_points == "0" and allies_points == "0":
            if "victory" in match_result or "win" in match_result:
                # Check if the player is on axis or allies
                player_id = match.get('player_id')
                axis_players = match.get('axis_players', [])
                allies_players = match.get('allies_players', [])
                
                axis_player_ids = [p.get('player_id') for p in axis_players if p.get('player_id')]
                allies_player_ids = [p.get('player_id') for p in allies_players if p.get('player_id')]
                
                if player_id in axis_player_ids:
                    axis_points = "500"
                elif player_id in allies_player_ids:
                    allies_points = "500"
        
        # Get player names
        axis_players = match.get('axis_players', [])
        allies_players = match.get('allies_players', [])
        
        # Pad player lists to ensure we have 4 entries for each side
        while len(axis_players) < 4:
            axis_players.append({"player_name": ""})
        while len(allies_players) < 4:
            allies_players.append({"player_name": ""})
        
        # Extract player names
        axis_player_names = [p.get('player_name', '') for p in axis_players[:4]]
        allies_player_names = [p.get('player_name', '') for p in allies_players[:4]]
        
        # Format row data
        row_data = [
            date_str,                      # Fecha
            time_str,                      # Hora
            match.get('map_name', ''),     # Mapa
            "Axis",                        # Ejército Eje (always "Axis")
            "Allies",                      # Ejército Aliados (always "Allies")
            *axis_player_names,            # Jugador Eje 1-4
            *allies_player_names,          # Jugador Aliados 1-4
            axis_points,                   # Puntos Eje
            allies_points,                 # Puntos Aliados
            match.get('unique_match_id', ''),  # Match ID
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Exportado (timestamp)
        ]
        
        return row_data
    
    def _get_existing_match_ids(self) -> List[str]:
        """Get list of match IDs already in the sheet"""
        try:
            # Get the Match ID column (column P or index 15)
            if not self.is_connected():
                return []
                
            all_values = self.worksheet.get_all_values()
            if len(all_values) <= 1:  # Only header row
                return []
                
            # Extract match IDs from column 16 (index 15), skipping header
            match_ids = [row[15] for row in all_values[1:] if len(row) > 15 and row[15]]
            return match_ids
            
        except Exception as e:
            logger.error(f"Error getting existing match IDs: {str(e)}")
            return []
    
    def export_matches(self, matches: List[Dict[str, Any]]) -> int:
        """Export matches to Google Sheets
        
        Args:
            matches: List of match data to export
            
        Returns:
            Number of matches exported
        """
        if not self.is_connected():
            logger.warning("Google Sheets client not connected. Cannot export matches.")
            return 0
            
        try:
            # Get existing match IDs to avoid duplicates
            existing_match_ids = self._get_existing_match_ids()
            logger.info(f"Found {len(existing_match_ids)} existing matches in sheet")
            
            # Filter out matches that are already in the sheet
            new_matches = [
                match for match in matches 
                if match.get('unique_match_id') not in existing_match_ids
            ]
            
            if not new_matches:
                logger.info("No new matches to export")
                return 0
                
            logger.info(f"Exporting {len(new_matches)} new matches to Google Sheets")
            
            # Format matches for the sheet
            rows_to_add = [self._format_match_for_sheet(match) for match in new_matches]
            
            # Get the next empty row
            next_row = len(self.worksheet.get_all_values()) + 1
            
            # Add new rows
            cell_range = f'A{next_row}:Q{next_row + len(rows_to_add) - 1}'
            self.worksheet.update(cell_range, rows_to_add)
            
            logger.info(f"Successfully exported {len(rows_to_add)} matches to Google Sheets")
            return len(rows_to_add)
            
        except Exception as e:
            logger.error(f"Error exporting matches to Google Sheets: {str(e)}")
            return 0 