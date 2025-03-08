import unittest
from unittest.mock import patch, MagicMock
from main import COH3StatsAnalyzer
from datetime import datetime
import mongomock
import os

# HTML de ejemplo para simular la respuesta de coh3stats.com
MOCK_HTML_RESPONSE = """
<div class="recent-matches">
    <div class="match-item" data-match-id="12345">
        <div class="match-date">2024-02-20 15:30</div>
        <div class="match-type">1v1</div>
        <div class="match-result">Victory</div>
        <div class="map-name">Fields of Normandy</div>
    </div>
</div>
"""

class TestCOH3StatsAnalyzer(unittest.TestCase):
    def setUp(self):
        # Configurar el mock de MongoDB
        self.mongo_patcher = patch('main.pymongo.MongoClient', mongomock.MongoClient)
        self.mongo_patcher.start()
        
        # Crear instancia del analizador
        self.analyzer = COH3StatsAnalyzer()
        
        # Datos de prueba
        self.test_player_id = "73550"
        self.test_player_name = "seju-fuminguez"

    def tearDown(self):
        self.mongo_patcher.stop()

    def test_add_player(self):
        """Prueba la función de añadir jugador"""
        self.analyzer.add_player(self.test_player_id, self.test_player_name)
        
        # Verificar que el jugador fue añadido
        player = self.analyzer.players_collection.find_one({"player_id": self.test_player_id})
        self.assertIsNotNone(player)
        self.assertEqual(player["player_name"], self.test_player_name)

    def test_get_players_to_analyze(self):
        """Prueba la función de obtener jugadores"""
        # Añadir algunos jugadores de prueba
        self.analyzer.add_player("12345", "test_player1")
        self.analyzer.add_player("67890", "test_player2")
        
        players = self.analyzer.get_players_to_analyze()
        self.assertEqual(len(players), 2)

    @patch('requests.get')
    def test_scrape_recent_match(self, mock_get):
        """Prueba la función de scraping de partidas"""
        # Configurar el mock de la respuesta HTTP
        mock_response = MagicMock()
        mock_response.text = MOCK_HTML_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Ejecutar el scraping
        match_data = self.analyzer.scrape_recent_match(
            self.test_player_id, 
            self.test_player_name
        )

        # Verificar los resultados
        self.assertIsNotNone(match_data)
        self.assertEqual(match_data["match_id"], "12345")
        self.assertEqual(match_data["match_type"], "1v1")
        self.assertEqual(match_data["match_result"], "Victory")
        self.assertEqual(match_data["map_name"], "Fields of Normandy")

    def test_analyze_all_players_empty_db(self):
        """Prueba el análisis cuando no hay jugadores en la BD"""
        result = self.analyzer.analyze_all_players()
        self.assertIsNone(result)

    @patch('requests.get')
    def test_analyze_all_players(self, mock_get):
        """Prueba el análisis de todos los jugadores"""
        # Añadir jugadores de prueba
        self.analyzer.add_player(self.test_player_id, self.test_player_name)
        
        # Configurar el mock de la respuesta HTTP
        mock_response = MagicMock()
        mock_response.text = MOCK_HTML_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Ejecutar el análisis
        self.analyzer.analyze_all_players()

        # Verificar que se guardó la partida
        match = self.analyzer.matches_collection.find_one({
            "player_id": self.test_player_id
        })
        self.assertIsNotNone(match)
        self.assertEqual(match["match_id"], "12345")

if __name__ == '__main__':
    unittest.main() 