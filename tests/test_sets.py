import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from game.modelos.db import get_db
from main import app


@pytest.fixture(name="session")
def dbTesting_fixture():
    # lightweight in-memory session reuse pattern from other tests
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from game.modelos.db import Base, get_session_local

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    def get_db_override():
        yield session

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("game.cartas.services.CartaService")
def test_obtener_sets_jugados_ok(mock_CartaService, client, session):
    """GET /partidas/{id}/sets debe devolver lo que retorna el servicio"""
    # preparar mock del servicio
    mock_service = MagicMock()
    mock_service.obtener_sets_jugados.return_value = [
        {"jugador_id": 1, "representacion_id_carta": 7, "cartas_ids": [7, 7, 7]},
        {"jugador_id": 2, "representacion_id_carta": 8, "cartas_ids": [8, 8, 8]},
    ]
    mock_CartaService.return_value = mock_service

    response = client.get("/partidas/1/sets")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert response.json()[0]["jugador_id"] == 1


@patch("game.cartas.services.CartaService")
@patch("game.partidas.endpoints.jugar_set_detective")
def test_jugar_set_ok(mock_jugar_set_detective, mock_CartaService, client, session):
    """POST /partidas/{id}/Jugar-set debe usar jugar_set_detective y devolver resumen"""
    # Mock manager (broadcast no-op async) and register as dependency override
    from game.partidas.endpoints import get_manager
    mgr = MagicMock()
    mgr.broadcast = AsyncMock()
    app.dependency_overrides[get_manager] = lambda: mgr

    # Mock cartas devueltas por la utilidad
    carta1 = MagicMock()
    carta1.id_carta = 7
    carta1.nombre = "Poirot"
    carta2 = MagicMock()
    carta2.id_carta = 7
    carta2.nombre = "Poirot"
    mock_jugar_set_detective.return_value = [carta1, carta2]

    # Mock servicio de persistencia que registra sets
    mock_service = MagicMock()
    mock_service.registrar_set_jugado.return_value = MagicMock()
    mock_CartaService.return_value = mock_service

    response = client.post("/partidas/1/Jugar-set?id_jugador=1&set_destino_id=0", json=[7, 7])

    app.dependency_overrides.pop(get_manager, None)

    assert response.status_code == 200
    body = response.json()
    assert body["detail"] == "Set jugado correctamente"
    assert isinstance(body["cartas_jugadas"], list)
    assert body["cartas_jugadas"][0]["id"] == 7
