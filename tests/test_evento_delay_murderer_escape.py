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
from game.partidas.models import Partida
from game.jugadores.models import Jugador
from game.cartas.models import Carta
from fastapi import WebSocketDisconnect
import json
from starlette.websockets import WebSocket
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

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

#---------------------Test delay the murderer escape ok----------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.utils.CartaService") 
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
def test_delay_murderer_scape_ok(mock_PartidaService, mock_JugadorService, mock_CartaService, session):
    """Test del evento Delay the Murderer Escape con todos los parametros ok"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_jugador = MagicMock()
    mock_jugador.id = 1
    mock_jugador.partida_id = 1

    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.obtener_por_id.return_value = SimpleNamespace(
        id_partida=1, iniciada=True, turno_id=1, jugadores=[mock_jugador]
    )
    mock_partida_service_instance.desgracia_social.return_value = False
    mock_PartidaService.return_value = mock_partida_service_instance

    mock_jugador_service_instance = MagicMock()
    mock_jugador_service_instance.obtener_jugador.return_value = mock_jugador
    mock_JugadorService.return_value = mock_jugador_service_instance

    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.jugar_delay_the_murderer_escape.return_value = None
    mock_carta_service_instance.obtener_cantidad_mazo.return_value = 10
    mock_carta_service_instance.obtener_cartas_descarte.return_value = [
        SimpleNamespace(id_carta=1, ubicacion="descarte")
    ]
    mock_carta_service_instance.obtener_mano_jugador.return_value = [
        SimpleNamespace(
            id_carta=23, tipo="Event", ubicacion="mano", nombre="Delay the murderer's escape!", partida_id=1
        )
    ]
    mock_carta_service_instance.obtener_carta_de_mano.return_value = SimpleNamespace(
        id_carta=23, tipo="Event", ubicacion="mano", nombre="Delay the murderer's escape!", partida_id=1
    )
    mock_CartaService.return_value = mock_carta_service_instance

    response = client.put(
        "/partidas/1/evento/DelayMurderer",
        params={"id_jugador": 1, "id_carta": 23, "cantidad": 1},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"detail": "Evento jugado correctamente"}

#---------------------Test delay the murderer escape desgracia social----------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.utils.CartaService")
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
def test_delay_murderer_scape_desgracia_social(mock_PartidaService, mock_JugadorService, mock_CartaService, session):
    """Test del evento Delay the Murderer Escape con un jugador en desgracia social"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_jugador = MagicMock()
    mock_jugador.id = 1
    mock_jugador.partida_id = 1

    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.obtener_por_id.return_value = MagicMock(
        id_partida=1, iniciada=True, turno_id=1, jugadores = [mock_jugador]
    )
    mock_partida_service_instance.desgracia_social.return_value = True
    mock_PartidaService.return_value = mock_partida_service_instance

    mock_jugador_service_instance = MagicMock()
    mock_jugador_service_instance.obtener_jugador.return_value = mock_jugador
    mock_JugadorService.return_value = mock_jugador_service_instance

    mock_carta_service_instance = MagicMock()
    carta_descarte = MagicMock()
    carta_descarte.id_carta = 1
    carta_descarte.ubicacion = "descarte"

    mock_carta_service_instance.obtener_cartas_descarte.return_value = [carta_descarte]
    mock_carta_service_instance.jugar_delay_the_murderer_escape.side_effect = None
    
    carta_evento = MagicMock(
        id_carta=23,
        tipo="Event",
        ubicacion="mano",
        nombre="Delay the murderer's escape!"
    )
    mock_carta_service_instance.obtener_mano_jugador.return_value = [carta_evento]
    mock_carta_service_instance.obtener_carta_de_mano.return_value = carta_evento
    mock_CartaService.return_value = mock_carta_service_instance

    response = client.put(
        "/partidas/1/evento/DelayMurderer",
        params={"id_jugador": 1, "id_carta": 23, "cantidad": 1},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {"detail": "El jugador 1 esta en desgracia social"}

#---------------------Test delay the murderer escape jugador con id inexistente----------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.utils.CartaService")
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
def test_delay_murderer_partida_inexistente(mock_PartidaService, mock_JugadorService, mock_CartaService, session):
    """Test Delay the Murderer Escape cuando la partida no se encuentra"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.obtener_por_id.return_value = None
    mock_PartidaService.return_value = mock_partida_service_instance

    mock_jugador_service_instance = MagicMock()
    mock_JugadorService.return_value = mock_jugador_service_instance

    mock_carta_service_instance = MagicMock()
    carta_descarte = MagicMock()
    carta_descarte.id_carta = 1
    carta_descarte.ubicacion = "descarte"

    mock_carta_service_instance.obtener_cartas_descarte.return_value = [carta_descarte]
    mock_carta_service_instance.jugar_delay_the_murderer_escape.side_effect = None
    mock_CartaService.return_value = mock_carta_service_instance

    response = client.put(
        "/partidas/1/evento/DelayMurderer",
        params={"id_jugador": 1, "id_carta": 23, "cantidad": 1},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "No se ha encontrado la partida con el ID:1"}
