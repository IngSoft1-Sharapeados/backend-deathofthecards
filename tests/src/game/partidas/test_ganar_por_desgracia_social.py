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

#----------------Test ganar por desgracia social ok------------
@patch("game.partidas.endpoints.ganar_por_desgracia_social")
@patch("game.partidas.endpoints.eliminarPartida")
@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.revelarSecreto")
@patch("game.partidas.endpoints.determinar_desgracia_social")
@patch("game.partidas.endpoints.obtener_jugador_por_id_carta")
def test_ganar_desgracia_social(mock_obtener_jugador_por_id_carta, mock_determinar_desgracia_social, mock_revelarSecreto, 
                                mock_CartaService, mock_manager, mock_ganar_por_desgracia_social, mock_eliminarPartida, session):
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_manager.broadcast = AsyncMock()
    mock_manager.clean_connections = AsyncMock()

    mock_obtener_jugador_por_id_carta.return_value = 2

    mock_determinar_desgracia_social.side_effect = [False, True]

    secreto_revelado = SimpleNamespace(id=65, jugador_id=2)
    mock_revelarSecreto.return_value = secreto_revelado

    carta_service_instance = MagicMock()
    secreto_b_revelado = SimpleNamespace(id=66, bocaArriba=True)
    secreto_b_no_revelado = SimpleNamespace(id=67, bocaArriba=False)
    carta_service_instance.obtener_secretos_jugador.return_value = [secreto_b_revelado, secreto_b_no_revelado]

    carta_service_instance.es_asesino.return_value = False
    carta_service_instance.es_complice.return_value = False

    mock_CartaService.return_value = carta_service_instance
    mock_ganar_por_desgracia_social.return_value = True  

    response = client.patch("/partidas/1/revelacion?id_jugador_turno=1&id_unico_secreto=65")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"id-secreto": 65}

    mock_obtener_jugador_por_id_carta.assert_called_once_with(1, 65, session)
    assert mock_determinar_desgracia_social.call_count == 2
    mock_revelarSecreto.assert_called_once_with(1, 1, 65, session)
    assert mock_manager.broadcast.await_count >= 1
    mock_ganar_por_desgracia_social.assert_called_once_with(1, session)
    assert mock_ganar_por_desgracia_social.return_value is True
    mock_manager.clean_connections.assert_awaited_once_with(1)
    mock_eliminarPartida.assert_called_once_with(1, session)


#----------------Test ganar asesino al revelar su secreto propio------------
@patch("game.partidas.endpoints.ganar_por_desgracia_social")
@patch("game.partidas.endpoints.eliminarPartida")
@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.revelarSecretoPropio")
@patch("game.partidas.endpoints.determinar_desgracia_social")
def test_revelar_secreto_propio_gana_asesino(mock_desgracia_social, mock_revelarSecretoPropio, mock_CartaService, 
                                             mock_manager, mock_eliminarPartida, mock_ganar_desgracia_social, session):

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_manager.broadcast = AsyncMock()
    mock_manager.clean_connections = AsyncMock()
    mock_desgracia_social.side_effect = [False, True]
    secreto_revelado = SimpleNamespace(id=65, jugador_id=2)
    mock_revelarSecretoPropio.return_value = secreto_revelado

    cs_instance = MagicMock()
    cs_instance.obtener_secretos_jugador.return_value = [
        SimpleNamespace(id=66, bocaArriba=True),
        SimpleNamespace(id=67, bocaArriba=False),
    ]
    cs_instance.es_asesino.return_value = False
    cs_instance.es_complice.return_value = False
    mock_CartaService.return_value = cs_instance

    mock_ganar_desgracia_social.return_value = True

    response = client.patch("/partidas/1/revelacion-propia?id_jugador=2&id_unico_secreto=65")

    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    assert response.json() == {"id-secreto": 65}

    mock_revelarSecretoPropio.assert_called_once_with(1, 2, 65, session)
    assert mock_desgracia_social.call_count == 2
    cs_instance.obtener_secretos_jugador.assert_called_once_with(secreto_revelado.jugador_id, 1)
    cs_instance.es_asesino.assert_called_once_with(65)
    mock_ganar_desgracia_social.assert_called_once_with(1, session)
    assert mock_ganar_desgracia_social.return_value is True
    assert mock_manager.broadcast.await_count >= 1
    mock_manager.clean_connections.assert_awaited_once_with(1)
    mock_eliminarPartida.assert_called_once_with(1, session)
