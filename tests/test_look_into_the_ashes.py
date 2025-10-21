import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch, ANY
from main import app
from game.modelos.db import get_db


# ---------- FIXTURE DB ----------
@pytest.fixture(name="session")
def dbTesting_fixture():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from game.modelos.db import Base, get_session_local

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session


# ---------- FIXTURE CLIENT ----------
@pytest.fixture(name="client")
def client_fixture(session):
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ---------- TESTS ----------

@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_evento")
def test_look_into_the_ashes_ok_evento(mock_verif_evento, mock_jugar_carta_evento, mock_manager, client):
    """Debe jugar el evento correctamente y enviar broadcast público."""
    mock_verif_evento.return_value = True
    mock_jugar_carta_evento.return_value = MagicMock()
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1&id_carta=10")

    assert response.status_code == 200
    mock_verif_evento.assert_called_once_with("Look into the ashes", 10)
    mock_jugar_carta_evento.assert_called_once_with(1, 1, 10, ANY)
    mock_manager.broadcast.assert_awaited_once()


@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.verif_evento")
def test_look_into_the_ashes_error_evento_invalido(mock_verif_evento, mock_manager, client):
    """Debe devolver 400 si la carta no corresponde al evento."""
    mock_verif_evento.return_value = False
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1&id_carta=99")

    assert response.status_code == 400
    assert "La carta no corresponde al evento" in response.json()["detail"]
    mock_manager.broadcast.assert_not_called()


@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_evento")
def test_look_into_the_ashes_error_value(mock_verif_evento, mock_jugar_carta_evento, mock_manager, client):
    """Debe mapear correctamente errores ValueError del servicio."""
    mock_verif_evento.return_value = True
    mock_jugar_carta_evento.side_effect = ValueError("Partida no iniciada")
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1&id_carta=11")

    assert response.status_code == 403
    assert "Partida no iniciada" in response.json()["detail"]
    mock_manager.broadcast.assert_not_called()


@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.jugar_look_into_ashes")
def test_look_into_the_ashes_ok_robo(mock_jugar_look_into_ashes, mock_manager, client):
    """Debe ejecutar correctamente la segunda fase (robar carta) y enviar broadcast."""
    mock_manager.broadcast = AsyncMock()
    mock_jugar_look_into_ashes.return_value = True

    response = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1&id_carta_objetivo=20")

    assert response.status_code == 200
    mock_jugar_look_into_ashes.assert_called_once_with(1, 1, 20, ANY)
    mock_manager.broadcast.assert_awaited_once()


@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.jugar_look_into_ashes")
def test_look_into_the_ashes_error_no_evento_previo(mock_jugar_look_into_ashes, mock_manager, client):
    """Debe devolver 400 si no se jugó el evento antes de intentar robar."""
    mock_jugar_look_into_ashes.side_effect = Exception("No se jugo el evento Look Into The Ashes")
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1&id_carta_objetivo=99")

    assert response.status_code == 400
    assert "No se jugo el evento Look Into The Ashes" in response.json()["detail"]
    mock_manager.broadcast.assert_not_called()


@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.jugar_look_into_ashes")
def test_look_into_the_ashes_error_carta_fuera_top5(mock_jugar_look_into_ashes, mock_manager, client):
    """Debe devolver 403 si la carta no está entre las top 5 del descarte."""
    mock_jugar_look_into_ashes.side_effect = Exception("La carta a robar no esta entre las top 5 cartas del mazo descarte")
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1&id_carta_objetivo=50")

    assert response.status_code == 403
    assert "top 5 cartas del mazo descarte" in response.json()["detail"]
    mock_manager.broadcast.assert_not_called()


def test_look_into_the_ashes_error_validacion(client):
    """Debe devolver 400 si se pasan ambos parámetros o ninguno."""
    # Ambos parámetros
    resp1 = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1&id_carta=10&id_carta_objetivo=20")
    # Ninguno
    resp2 = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1")

    for resp in [resp1, resp2]:
        assert resp.status_code == 400
        assert "Error de validacion" in resp.json()["detail"]


# ---------- TESTS DE ERRORES ADICIONALES (COBERTURA DE RAISES) ----------

@pytest.mark.parametrize("msg,expected_status", [
    ("no se encontro", 404),
    ("no pertenece a la partida", 403),
    ("no esta en turno", 403),
    ("una carta de evento por turno", 400),
    ("La carta no se encuentra en la mano del jugador", 400),
    ("no es de tipo evento", 400),
    ("inesperado", 500),
])
@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_evento")
def test_look_into_the_ashes_mapeo_excepciones(mock_verif_evento, mock_jugar_carta_evento, mock_manager, client, msg, expected_status):
    """Debe mapear correctamente todos los ValueError posibles del servicio."""
    mock_verif_evento.return_value = True
    mock_jugar_carta_evento.side_effect = ValueError(msg)
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/LookIntoTheAshes?id_jugador=1&id_carta=10")

    assert response.status_code == expected_status
    assert msg in response.json()["detail"]
    mock_manager.broadcast.assert_not_called()