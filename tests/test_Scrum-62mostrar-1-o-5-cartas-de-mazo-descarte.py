import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from main import app
from game.modelos.db import get_db


# ---------- FIXTURE DE DB ----------
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

@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
@patch("game.partidas.utils.CartaService")
@patch("game.partidas.endpoints.manager")
def test_obtener_cartas_descarte_ok_una(mock_manager, mock_CartaService, mock_PartidaService, mock_JugadorService, client):
    """Debe devolver una carta y enviar broadcast público."""
    mock_manager.broadcast = AsyncMock()

    mock_PartidaService.return_value.obtener_por_id.return_value = MagicMock()
    mock_jugador = MagicMock(partida_id=1)
    mock_JugadorService.return_value.obtener_jugador.return_value = mock_jugador

    mock_carta = MagicMock()
    mock_carta.id_carta = 3
    mock_carta.nombre = "Dead Card Folly"
    mock_CartaService.return_value.obtener_cartas_descarte.return_value = [mock_carta]

    response = client.get("/partidas/1/descarte?id_jugador=1&cantidad=1")

    assert response.status_code == 200
    assert response.json() == [{"id": 3, "nombre": "Dead Card Folly"}]
    mock_CartaService.return_value.obtener_cartas_descarte.assert_called_once_with(1, 1)
    mock_manager.broadcast.assert_awaited_once()


@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
@patch("game.partidas.utils.CartaService")
@patch("game.partidas.endpoints.manager")
def test_obtener_cartas_descarte_ok_cinco(mock_manager, mock_CartaService, mock_PartidaService, mock_JugadorService, client):
    """Debe devolver 5 cartas y enviar mensaje privado."""
    mock_manager.send_personal_message = AsyncMock()

    mock_PartidaService.return_value.obtener_por_id.return_value = MagicMock()
    mock_jugador = MagicMock(partida_id=1)
    mock_JugadorService.return_value.obtener_jugador.return_value = mock_jugador

    cartas = []
    for i in range(5):
        carta = MagicMock()
        carta.id_carta = i + 1
        carta.nombre = f"Carta {i + 1}"
        cartas.append(carta)

    mock_CartaService.return_value.obtener_cartas_descarte.return_value = cartas

    response = client.get("/partidas/1/descarte?id_jugador=1&cantidad=5")

    assert response.status_code == 200
    assert response.json() == [{"id": i + 1, "nombre": f"Carta {i + 1}"} for i in range(5)]
    mock_CartaService.return_value.obtener_cartas_descarte.assert_called_once_with(1, 5)
    mock_manager.send_personal_message.assert_awaited_once()


@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
@patch("game.partidas.utils.CartaService")
def test_obtener_cartas_descarte_cantidad_invalida(mock_CartaService, mock_PartidaService, mock_JugadorService, client):
    """Debe devolver 400 si la cantidad no es 1 ni 5."""
    mock_PartidaService.return_value.obtener_por_id.return_value = MagicMock()
    mock_JugadorService.return_value.obtener_jugador.return_value = MagicMock(partida_id=1)

    response = client.get("/partidas/1/descarte?id_jugador=1&cantidad=3")

    assert response.status_code == 400
    assert "Solo se mostrara 1 o las 5 ultimas cartas del mazo de descarte" in response.json()["detail"]
    mock_CartaService.return_value.obtener_cartas_descarte.assert_not_called()


@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
@patch("game.partidas.utils.CartaService")
def test_obtener_cartas_descarte_partida_no_encontrada(mock_CartaService, mock_PartidaService, mock_JugadorService, client):
    """Debe devolver 404 si la partida no existe."""
    mock_PartidaService.return_value.obtener_por_id.return_value = None
    mock_JugadorService.return_value.obtener_jugador.return_value = MagicMock(partida_id=1)

    response = client.get("/partidas/999/descarte?id_jugador=1&cantidad=1")

    assert response.status_code == 404
    assert "No se encontro la partida" in response.json()["detail"]
    mock_CartaService.return_value.obtener_cartas_descarte.assert_not_called()


@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
@patch("game.partidas.utils.CartaService")
def test_obtener_cartas_descarte_error_interno(mock_CartaService, mock_PartidaService, mock_JugadorService, client):
    """Debe devolver 500 si ocurre un error interno en el servicio."""
    mock_PartidaService.return_value.obtener_por_id.return_value = MagicMock()
    mock_JugadorService.return_value.obtener_jugador.return_value = MagicMock(partida_id=1)
    mock_CartaService.return_value.obtener_cartas_descarte.side_effect = Exception("Error interno simulado")

    response = client.get("/partidas/1/descarte?id_jugador=1&cantidad=5")

    assert response.status_code == 500
    assert "No se pudo obtener las cartas del mazo descarte" in response.json()["detail"]