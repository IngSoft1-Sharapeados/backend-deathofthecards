import pytest
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from main import app
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from game.modelos.db import get_db
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from game.modelos.db import Base, get_db, get_session_local
from game.partidas.utils import *


# ---------- FIXTURE DE DB ----------
@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session


@patch('game.partidas.endpoints.CartaService')
@patch('game.partidas.utils.CartaService')
@patch('game.partidas.utils.JugadorService')
@patch('game.partidas.utils.PartidaService')
def test_robar_secreto_otro_jugador_ok(
    mock_PartidaService,
    mock_JugadorService,
    mock_CartaService_utils,
    #mock_CartaService_endpoint,
    session
):
    """
    Test robar secreto en caso de éxito
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)
    
    partida_mock = MagicMock(id=1, turno_id=1)

    jugador_turno = MagicMock(id=1)
    jugador_destino = MagicMock(id=2)

    carta_mock = MagicMock(id=1, bocaArriba=True, jugador_id=2, partida_id=1, tipo="secreto")

    # Retorno de CartaService (endpoint y utils apuntan al mismo, así que se mockean ambos)
    carta_service_instance = MagicMock()
    carta_service_instance.obtener_carta_por_id.return_value = carta_mock
    carta_service_instance.robar_secreto.return_value = {"id-secreto": carta_mock.id}
    mock_CartaService_utils.return_value = carta_service_instance
    #mock_CartaService_endpoint.return_value = carta_service_instance

    jugador_service_instance = MagicMock()
    jugador_service_instance.obtener_jugador.side_effect = lambda id: jugador_turno if id == 1 else jugador_destino
    mock_JugadorService.return_value = jugador_service_instance

    partida_service_instance = MagicMock()
    partida_service_instance.obtener_por_id.return_value = partida_mock
    mock_PartidaService.return_value = partida_service_instance

    response = client.patch(
        "partidas/1/robo-secreto",
        params={
            "id_jugador_turno": 1,
            "id_jugador_destino": 2,
            "id_unico_secreto": 1
        }
    )

    assert response.status_code == 200
    assert response.json() == {"id-secreto": 1}
    carta_service_instance.obtener_carta_por_id.assert_called_once_with(1)
    carta_service_instance.robar_secreto.assert_called_once_with(carta_mock, 2)

    app.dependency_overrides.clear()


@patch('game.partidas.endpoints.CartaService')
@patch('game.partidas.endpoints.robar_secreto')
@patch('game.partidas.utils.CartaService')
@patch('game.partidas.utils.JugadorService')
@patch('game.partidas.utils.PartidaService')
def test_robar_secreto_oculto(mock_partida_service, mock_jugador_service, mock_carta_service, mock_robar_secreto, session):
    """Test fallo al querer robar un secreto que está oculto"""
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    partida_mock = MagicMock()
    partida_mock.id = 1
    partida_mock.turno_id = 1

    jugador_turno = MagicMock()
    jugador_turno.id = 1

    jugador_destino = MagicMock()
    jugador_destino.id = 2

    carta_secreta = MagicMock()
    carta_secreta.id = 1
    carta_secreta.jugador_id = 1
    carta_secreta.bocaArriba = False  # Oculto
    carta_secreta.partida_id = 1

    mock_partida_service.return_value.obtener_por_id.return_value = partida_mock
    mock_jugador_service.return_value.obtener_jugador.side_effect = lambda id: jugador_turno if id == 1 else jugador_destino
    mock_carta_service.return_value.obtener_carta_por_id.return_value = carta_secreta

    mock_robar_secreto.side_effect = ValueError("No se puede robar un secreto que está oculto!")

    response = client.patch("/partidas/1/robo-secreto?id_jugador_turno=1&id_jugador_destino=2&id_unico_secreto=1")

    assert response.status_code == 401
    assert "No se puede robar un secreto que está oculto" in response.json()["detail"]

    app.dependency_overrides.clear()