import requests
from bs4 import BeautifulSoup
import pymongo
from datetime import datetime
import time
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://usuario:contraseña@cluster0.mongodb.net/")
DB_NAME = "coh3stats_db"
PLAYERS_COLLECTION = "players"
MATCHES_COLLECTION = "matches"

class COH3StatsAnalyzer:
    def __init__(self):
        # Conectar a MongoDB
        self.client = pymongo.MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.players_collection = self.db[PLAYERS_COLLECTION]
        self.matches_collection = self.db[MATCHES_COLLECTION]
        
    def get_players_to_analyze(self):
        """Obtiene la lista de jugadores a analizar desde la base de datos"""
        return list(self.players_collection.find({}))
    
    def add_player(self, player_id, player_name):
        """Añade un nuevo jugador a la base de datos"""
        player_data = {
            "player_id": player_id,
            "player_name": player_name,
            "added_at": datetime.now()
        }
        self.players_collection.update_one(
            {"player_id": player_id},
            {"$set": player_data},
            upsert=True
        )
        print(f"Jugador {player_name} (ID: {player_id}) añadido correctamente")
    
    def scrape_recent_match(self, player_id, player_name):
        """Obtiene la información de la última partida de un jugador"""
        url = f"https://coh3stats.com/players/{player_id}/{player_name}?view=recentMatches"
        
        try:
            # Realizar la petición HTTP
            response = requests.get(url)
            response.raise_for_status()
            
            # Parsear el HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Encontrar la última partida (esto dependerá de la estructura HTML de la página)
            # Nota: Es posible que necesites ajustar estos selectores según la estructura real
            match_container = soup.select_one('.recent-matches .match-item')
            
            if not match_container:
                print(f"No se encontraron partidas recientes para {player_name}")
                return None
            
            # Extraer información de la partida
            match_id = match_container.get('data-match-id', '')
            match_date = match_container.select_one('.match-date').text.strip()
            match_type = match_container.select_one('.match-type').text.strip()
            match_result = match_container.select_one('.match-result').text.strip()
            map_name = match_container.select_one('.map-name').text.strip()
            
            # Crear objeto de partida
            match_data = {
                "match_id": match_id,
                "player_id": player_id,
                "player_name": player_name,
                "match_date": match_date,
                "match_type": match_type,
                "match_result": match_result,
                "map_name": map_name,
                "scraped_at": datetime.now()
            }
            
            # Guardar en la base de datos si no existe
            if not self.matches_collection.find_one({"match_id": match_id, "player_id": player_id}):
                self.matches_collection.insert_one(match_data)
                print(f"Nueva partida guardada para {player_name}: {match_id}")
                return match_data
            else:
                print(f"La partida {match_id} ya existe en la base de datos")
                return None
                
        except Exception as e:
            print(f"Error al obtener datos de {player_name}: {str(e)}")
            return None
    
    def analyze_all_players(self):
        """Analiza las últimas partidas de todos los jugadores en la base de datos"""
        players = self.get_players_to_analyze()
        
        if not players:
            print("No hay jugadores en la base de datos para analizar")
            return
        
        for player in players:
            player_id = player["player_id"]
            player_name = player["player_name"]
            
            print(f"Analizando jugador: {player_name}")
            match_data = self.scrape_recent_match(player_id, player_name)
            
            # Esperar un poco entre peticiones para no sobrecargar el servidor
            time.sleep(2)

def main():
    analyzer = COH3StatsAnalyzer()
    
    while True:
        try:
            # Analizar todos los jugadores
            analyzer.analyze_all_players()
            
            # Esperar 5 minutos antes de la siguiente ejecución
            time.sleep(300)
        except Exception as e:
            print(f"Error en el ciclo principal: {str(e)}")
            time.sleep(60)  # Esperar 1 minuto si hay error

if __name__ == "__main__":
    main()
