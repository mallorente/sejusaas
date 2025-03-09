import unittest
import requests
import pymongo
from main import COH3StatsAnalyzer
import os
from dotenv import load_dotenv
import time

class TestConnections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Cargar variables de entorno
        load_dotenv()
        cls.mongo_uri = os.getenv("MONGO_URI")
        
        if not cls.mongo_uri:
            raise ValueError("MONGO_URI no está configurado en el archivo .env")

    def test_mongo_connection(self):
        """Prueba la conexión real a MongoDB"""
        try:
            # Intentar conexión a MongoDB
            client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            # Forzar la conexión
            client.server_info()
            
            self.assertTrue(True, "Conexión a MongoDB exitosa")
            
            # Prueba básica de operaciones CRUD
            db = client.test_database
            collection = db.test_collection
            
            # Create
            test_doc = {"test": "data", "timestamp": time.time()}
            result = collection.insert_one(test_doc)
            self.assertTrue(result.inserted_id is not None)
            
            # Read
            found_doc = collection.find_one({"_id": result.inserted_id})
            self.assertIsNotNone(found_doc)
            
            # Update
            update_result = collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"test": "updated_data"}}
            )
            self.assertEqual(update_result.modified_count, 1)
            
            # Delete
            delete_result = collection.delete_one({"_id": result.inserted_id})
            self.assertEqual(delete_result.deleted_count, 1)
            
            # Limpiar
            collection.drop()
            client.close()
            
        except pymongo.errors.ServerSelectionTimeoutError:
            self.fail("No se pudo conectar a MongoDB - Timeout")
        except pymongo.errors.ConnectionError:
            self.fail("Error de conexión a MongoDB")
        except Exception as e:
            self.fail(f"Error inesperado al conectar a MongoDB: {str(e)}")

    def test_coh3stats_connection(self):
        """Prueba la conexión y respuesta de coh3stats.com"""
        test_player_id = "73550"
        test_player_name = "seju-fuminguez"
        url = f"https://coh3stats.com/players/{test_player_id}/{test_player_name}?view=recentMatches"
        
        try:
            # Prueba de conexión básica
            response = requests.get("https://coh3stats.com")
            self.assertEqual(response.status_code, 200, "El sitio coh3stats.com está accesible")
            
            # Prueba de endpoint específico
            response = requests.get(url)
            self.assertEqual(response.status_code, 200, "El endpoint de jugador está accesible")
            
            # Verificar que la respuesta contiene HTML válido
            self.assertTrue(
                response.text.lower().startswith('<!doctype html>') or 
                response.text.lower().startswith('<!DOCTYPE html>'),
                "La respuesta debe contener un doctype HTML válido"
            )
            
            # Verificar que la respuesta contiene elementos HTML básicos
            self.assertIn('<html', response.text.lower(), "La respuesta debe contener una etiqueta HTML")
            self.assertIn('<head', response.text.lower(), "La respuesta debe contener una etiqueta HEAD")
            self.assertIn('<body', response.text.lower(), "La respuesta debe contener una etiqueta BODY")
            
            # Verificar rate limiting
            headers = response.headers
            if 'X-RateLimit-Remaining' in headers:
                remaining_calls = int(headers['X-RateLimit-Remaining'])
                self.assertGreaterEqual(
                    remaining_calls, 
                    0, 
                    "Hay llamadas API disponibles"
                )
            
        except requests.exceptions.ConnectionError:
            self.fail("No se pudo conectar a coh3stats.com")
        except requests.exceptions.Timeout:
            self.fail("Timeout al conectar a coh3stats.com")
        except requests.exceptions.RequestException as e:
            self.fail(f"Error al hacer request a coh3stats.com: {str(e)}")

    def test_analyzer_integration(self):
        """Prueba la integración completa del analizador"""
        try:
            analyzer = COH3StatsAnalyzer()
            
            # Prueba añadir jugador
            test_player_id = "73550"
            test_player_name = "seju-fuminguez"
            analyzer.add_player(test_player_id, test_player_name)
            
            # Verificar que se añadió correctamente
            players = analyzer.get_players_to_analyze()
            self.assertTrue(any(p["player_id"] == test_player_id for p in players))
            
            # Prueba obtener partida reciente
            match_data = analyzer.scrape_recent_match(test_player_id, test_player_name)
            
            if match_data:
                self.assertIsInstance(match_data, dict)
                required_fields = [
                    "match_id", "player_id", "player_name", 
                    "match_date", "match_type", "match_result", "map_name"
                ]
                for field in required_fields:
                    self.assertIn(field, match_data)
            
            # Limpiar datos de prueba
            analyzer.players_collection.delete_many({"player_id": test_player_id})
            analyzer.matches_collection.delete_many({"player_id": test_player_id})
            
        except Exception as e:
            self.fail(f"Error en la prueba de integración: {str(e)}")

if __name__ == '__main__':
    unittest.main(verbosity=2) 