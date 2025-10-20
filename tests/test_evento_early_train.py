import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace
from sqlalchemy.pool import StaticPool

# --- Bloque de Configuración ---
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from main import app
from game.modelos.db import Base, get_db, get_session_local

@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session
# --- Fin del Bloque de Configuración ---


#--------------------- Test Early Train OK --------------------------
# ARREGLO: Añadimos patch para las funciones de utilidad que se llaman dentro del endpoint
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_evento")
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
def test_early_train_ok(mock_PartidaService, mock_JugadorService, mock_CartaService_endpoints, mock_verif_evento, mock_jugar_carta_evento, session):
    """Test del evento Early train to paddington con todos los parámetros ok."""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mocks de validación
    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.obtener_por_id.return_value = SimpleNamespace(iniciada=True, turno_id=1)
    mock_partida_service_instance.desgracia_social.return_value = False
    mock_PartidaService.return_value = mock_partida_service_instance
    
    mock_jugador_service_instance = MagicMock()
    mock_jugador_service_instance.obtener_jugador.return_value = SimpleNamespace(id=1, partida_id=1)
    mock_JugadorService.return_value = mock_jugador_service_instance

    # ARREGLO: Mockeamos el comportamiento de las funciones de utilidad
    mock_verif_evento.return_value = True
    mock_jugar_carta_evento.return_value = None

    # Mock del servicio de cartas
    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.jugar_early_train_to_paddington.return_value = None
    mock_carta_service_instance.obtener_cantidad_mazo.return_value = 10
    mock_carta_service_instance.obtener_cartas_descarte.return_value = []
    mock_CartaService_endpoints.return_value = mock_carta_service_instance

    response = client.put(
        "/partidas/1/evento/EarlyTrain",
        params={"id_jugador": 1, "id_carta": 24},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"detail": "Evento jugado correctamente"}
    mock_jugar_carta_evento.assert_called_once_with(1, 1, 24, session)
    mock_carta_service_instance.jugar_early_train_to_paddington.assert_called_once_with(1, 1)


#--------------------- Test Early Train Partida Inexistente --------------------------
@patch("game.partidas.utils.PartidaService")
def test_early_train_partida_inexistente(mock_PartidaService, session):
    """Test del evento Early Train cuando la partida no existe."""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.obtener_por_id.return_value = None
    mock_PartidaService.return_value = mock_partida_service_instance

    response = client.put(
        "/partidas/999/evento/EarlyTrain",
        params={"id_jugador": 1, "id_carta": 24},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "No se ha encontrado la partida" in response.json()["detail"]