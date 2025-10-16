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

#----------- Test jugar carta de evento Cards off the table OK-----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.jugar_carta_evento")
def test_cards_off_the_table_completo(mock_jugar_carta_evento, mock_CartaService, session):
    """Test completo para Cards off the table usando la lógica del endpoint con mocks de cartas"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    carta_evento = MagicMock(id_carta=17, tipo="Event", ubicacion="mano", nombre="Cards off the table")
    
    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.obtener_mano_jugador.return_value = [carta_evento]
    mock_carta_service_instance.obtener_carta_de_mano.return_value = carta_evento

    mock_carta_service_instance.evento_jugado_en_turno.return_value = False
    mock_carta_service_instance.jugar_cards_off_the_table.return_value = None
    mock_CartaService.return_value = mock_carta_service_instance

    mock_jugar_carta_evento.return_value = carta_evento

    response = client.put(
        "/partidas/1/evento/CardsTable?id_jugador=1&id_objetivo=2&id_carta=17"
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"detail": "Evento jugado correctamente"}
    mock_carta_service_instance.jugar_cards_off_the_table.assert_called_once_with(1, 1, 2)
    
#----------------------Test de jugar cards off the table con un id inexistente ----------------------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.utils.PartidaService")
def test_evento_partida_inexistente(mock_PartidaService, mock_CartaService, session):
    """Test para verificar que se maneja correctamente el caso cuando no existe la id de partida"""
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.obtener_por_id.return_value = None
    mock_PartidaService.return_value = mock_partida_service_instance

    mock_carta_service_instance = MagicMock()
    mock_CartaService.return_value = mock_carta_service_instance

    response = client.put(
        "/partidas/999/evento/CardsTable?id_jugador=1&id_objetivo=2&id_carta=17"
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "No se ha encontrado la partida con el ID:999"}
    mock_partida_service_instance.obtener_por_id.assert_called_once_with(999)

#----------- Test se juega evento Cards off the table jugador inexistente--------------
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
@patch("game.partidas.endpoints.CartaService")
def test_cards_off_the_table_jugador_no_encontrado(mock_CartaService, mock_PartidaService, mock_JugadorService, session):
    """Test cuando el jugador no se encuentra en la partida"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.obtener_por_id.return_value = MagicMock(
        id_partida=1, iniciada=True, turno_id=1
    )
    mock_PartidaService.return_value = mock_partida_service_instance
    mock_jugador_service_instance = MagicMock()
    mock_jugador_service_instance.obtener_jugador.return_value = None
    mock_JugadorService.return_value = mock_jugador_service_instance

    mock_carta_service_instance = MagicMock()
    mock_CartaService.return_value = mock_carta_service_instance

    response = client.put(
        "/partidas/1/evento/CardsTable?id_jugador=999&id_objetivo=2&id_carta=17"
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "No se encontro el jugador 999."}
    mock_partida_service_instance.obtener_por_id.assert_called_once_with(1)
    mock_jugador_service_instance.obtener_jugador.assert_called_once_with(999)
