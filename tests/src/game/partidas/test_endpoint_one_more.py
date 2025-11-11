import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from game.modelos.db import Base, get_db, get_session_local
from main import app

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

#----------- Test 1: jugar evento One More completo y exitoso -----------------
@patch("game.partidas.endpoints.manager.broadcast", new_callable=AsyncMock)
@patch("game.cartas.services.CartaService")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.utils.JugadorService")
def test_one_more_completo(mock_JugadorService, mock_verif_jugador, mock_jugar_evento, mock_CartaService, mock_broadcast, session):
    """Test completo para And then there was one more..."""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # Mock del servicio de jugadores
    mock_jugador_service = MagicMock()
    mock_jugador_destino = MagicMock(id=3, partida_id=1)
    mock_jugador_service.obtener_jugador.return_value = mock_jugador_destino
    mock_JugadorService.return_value = mock_jugador_service

    # Mock de verificación de jugador objetivo
    mock_verif_jugador.return_value = None

    # Mock del secreto a trasladar
    secreto_mock = MagicMock(
        id_carta=50,
        tipo="secreto",
        bocaArriba=True,
        jugador_id=2,  # jugador fuente
        partida_id=1
    )

    # Mock de las listas de secretos
    secretos_fuente = [secreto_mock]
    secretos_destino = [MagicMock(bocaArriba=False)]

    # Mock del servicio de cartas
    mock_carta_service = MagicMock()
    mock_carta_service.obtener_carta_por_id.return_value = secreto_mock
    mock_carta_service.robar_secreto.return_value = None
    mock_carta_service.descartar_cartas.return_value = None
    mock_carta_service.obtener_secretos_jugador.side_effect = [secretos_fuente, secretos_destino]
    mock_CartaService.return_value = mock_carta_service

    # Mock de jugar_carta_evento
    carta_evento = MagicMock(id_carta=22, nombre="And then there was one more...")
    mock_jugar_evento.return_value = carta_evento

    # Mock de la query para la carta evento
    mock_query = MagicMock()
    mock_query.filter_by.return_value.first.return_value = carta_evento
    session.query = MagicMock(return_value=mock_query)

    payload = {
        "id_fuente": 2,
        "id_destino": 3,
        "id_unico_secreto": 50
    }

    response = client.put(
        "/partidas/1/evento/OneMore?id_jugador=1&id_carta=22",
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"detail": "Evento jugado correctamente"}
    mock_carta_service.robar_secreto.assert_called_once_with(secreto_mock, 3)

#----------- Test 2: carta incorrecta (no es "And then there was one more...") -----------------
@patch("game.partidas.utils.JugadorService")
def test_one_more_carta_incorrecta(mock_JugadorService, session):
    """Test cuando se intenta jugar una carta que no es And then there was one more..."""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    payload = {
        "id_fuente": 2,
        "id_destino": 3,
        "id_unico_secreto": 50
    }

    response = client.put(
        "/partidas/1/evento/OneMore?id_jugador=1&id_carta=999",  # ID inválido
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "La carta no corresponde al evento And then there was one more..." in response.json()["detail"]

#----------- Test 3: jugador destino no existe -----------------
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.utils.JugadorService")
def test_one_more_jugador_destino_inexistente(mock_JugadorService, mock_verif_jugador, session):
    """Test cuando el jugador destino no existe"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # Mock de verificación OK para el jugador fuente
    mock_verif_jugador.return_value = None

    # Mock del servicio - jugador destino no existe
    mock_jugador_service = MagicMock()
    mock_jugador_service.obtener_jugador.return_value = None
    mock_JugadorService.return_value = mock_jugador_service

    payload = {
        "id_fuente": 2,
        "id_destino": 999,
        "id_unico_secreto": 50
    }

    response = client.put(
        "/partidas/1/evento/OneMore?id_jugador=1&id_carta=22",
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "No se encontró el jugador destino 999" in response.json()["detail"]
