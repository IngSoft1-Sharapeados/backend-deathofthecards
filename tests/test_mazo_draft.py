import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from game.modelos.db import Base, get_db, get_engine, get_session_local
from settings import settings
from main import app
from game.partidas.endpoints import get_manager
from fastapi import WebSocketDisconnect
import json
from starlette.websockets import WebSocket
from sqlalchemy.pool import StaticPool

# Base de datos en memoria
@pytest.fixture(name="session")
def dbTesting_fixture():

    engine = (
        create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
        )
    )
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session

#-----------------Test de obtener mazo de draft ok----------------------
@patch("game.partidas.utils.CartaService")
@patch("game.partidas.utils.PartidaService")
def test_obtener_mazo_draft(mock_PartidaService, mock_CartaService, session):
    """Test para verificar que se obtiene correctamente el mazo de draft"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock PartidaService
    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.obtener_por_id.return_value = 1
    mock_PartidaService.return_value = mock_partida_service_instance

    # Mock CartaService
    mock_carta_1 = MagicMock(id_carta=14, nombre="Harley Quin Wildcard")
    mock_carta_2 = MagicMock(id_carta=26, nombre="Blackmailed")
    mock_carta_3 = MagicMock(id_carta=25, nombre="Point your suspicions")
    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.obtener_mazo_draft.return_value = [mock_carta_1, mock_carta_2, mock_carta_3]
    mock_CartaService.return_value = mock_carta_service_instance

    # Act
    response = client.get("/partidas/1/draft")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {"id": 14, "nombre": "Harley Quin Wildcard"},
        {"id": 26, "nombre": "Blackmailed"},
        {"id": 25, "nombre": "Point your suspicions"}
    ]

#----------------------Test robar carta draft ok-----------------------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.PartidaService")
def test_accion_recoger_cartas(mock_PartidaService, mock_CartaService, session):
    """Test para verificar que un jugador recoge una carta del draft correctamente"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_partida_service_instance = MagicMock()
    carta_mock = MagicMock()
    carta_mock.id_carta = 16
    carta_mock.nombre = "Not so fast"
    mock_partida_service_instance.manejar_accion_recoger.return_value = {
        "nuevas_cartas": [{"id": 16, "nombre": "Not so fast"}],
        "nuevo_turno_id": 2,
        "nuevo_draft": [carta_mock],
        "cantidad_final_mazo": 50
    }
    mock_PartidaService.return_value = mock_partida_service_instance
    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.tomar_cartas_draft.return_value = None
    mock_CartaService.return_value = mock_carta_service_instance

    response = client.put(
        "/partidas/1/jugador/1/recoger",
        json={"cartas_draft": [16]}
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [{"id": 16, "nombre": "Not so fast"}]

#----------------------Test robar carta draft con un id inexistente ----------------------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.PartidaService")
def test_accion_recoger_cartas_partida_inexistente(mock_PartidaService, mock_CartaService, session):
    """Test para verificar que se maneja correctamente el caso cuando no existe la id de partida"""
    
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.manejar_accion_recoger.side_effect = HTTPException(status_code=404, detail="Partida no encontrada")
    mock_PartidaService.return_value = mock_partida_service_instance

    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.tomar_cartas_draft.return_value = None
    mock_CartaService.return_value = mock_carta_service_instance

    response = client.put(
        "/partidas/999/jugador/1/recoger", 
        json={"cartas_draft": [16]}
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404  
    assert response.json() == {"detail": "Partida no encontrada"}  
