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


# Test Abandono por Invitado (con 2 jugadores en la partida)
@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_abandonar_partida_invitado(mock_JugadorService, mock_PartidaService, session):
    """
    Test de abandono por un jugador invitado con una partida de 2 jugadores (anfitrión + invitado)
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # Crear un mock de la partida con 2 jugadores
    partida_mock = MagicMock(id=1, anfitrionId=1, iniciada=False)
    
    # Crear dos jugadores, uno es el anfitrión y el otro es un invitado
    jugador_anfitrion = MagicMock(id=1, nombre="Anfitrión", partida_id=1)
    jugador_invitado = MagicMock(id=2, nombre="Jugador Invitado", partida_id=1)

    # Simular la lista de jugadores en la partida
    partida_mock.jugadores = [jugador_anfitrion, jugador_invitado]

    # Configuración de los mocks
    # Devolvemos un diccionario serializable con los datos del jugador
    mock_JugadorService.return_value = MagicMock(obtener_jugador=MagicMock(return_value=jugador_invitado))
    
    # Simulamos la respuesta del servicio PartidaService
    mock_PartidaService.return_value = MagicMock(obtener_por_id=MagicMock(return_value=partida_mock))

    # Simulamos la respuesta que debe devolver el endpoint
    mock_PartidaService.return_value.actualizar_cant_jugadores.return_value = 1  # Después del abandono, solo queda el anfitrión

    # Realizar el request
    response = client.post(f"/partidas/{1}/abandonar?id_jugador=2")

    # Verificaciones
    assert response.status_code == 200
    assert response.json() == {
        "rol": "invitado",
        "id_jugador": 2,
        "nombre_jugador": "Jugador Invitado",
        "jugadoresRestantes": 1  # Después de que el invitado abandona, queda solo el anfitrión
    }

    # Verificar que el mock de jugador fue llamado correctamente
    mock_JugadorService.return_value.obtener_jugador.assert_called_once_with(2)
    mock_PartidaService.return_value.obtener_por_id.assert_called_once_with(1)

    app.dependency_overrides.clear()


@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_abandonar_partida_iniciada(mock_JugadorService, mock_PartidaService, session):
    """
    Test de abandono de partida cuando ya ha sido iniciada
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # Crear un mock de la partida ya iniciada
    partida_mock = MagicMock(id=1, anfitrionId=1, iniciada=True)  # La partida está iniciada
    
    jugador_invitado = MagicMock(id=2, nombre="Jugador Invitado", partida_id=1)

    # Configuración de los mocks
    mock_JugadorService.return_value = MagicMock(obtener_jugador=MagicMock(return_value=jugador_invitado))
    mock_PartidaService.return_value = MagicMock(obtener_por_id=MagicMock(return_value=partida_mock))

    # Realizar el request
    response = client.post(f"/partidas/1/abandonar?id_jugador=2")

    # Verificaciones
    assert response.status_code == 401  # Debería devolver error 401
    assert "No se puede abandonar la partida una vez iniciada" in response.json()["detail"]

    app.dependency_overrides.clear()


@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_abandonar_partida_no_encontrada(mock_JugadorService, mock_PartidaService, session):
    """
    Test de abandono de partida cuando no se encuentra la partida o el jugador
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # Simulamos que no se encuentra la partida o el jugador
    mock_JugadorService.return_value = MagicMock(obtener_jugador=MagicMock(return_value=None))  # No se encuentra el jugador
    mock_PartidaService.return_value = MagicMock(obtener_por_id=MagicMock(return_value=None))  # No se encuentra la partida

    # Intentar abandonar una partida con un jugador o partida inexistente
    response = client.post(f"/partidas/{1}/abandonar?id_jugador=99")  # Usamos un ID de jugador que no existe

    # Verificaciones
    assert response.status_code == 404  # Debería devolver error 404
    assert "No se ha encontrado la partida con el ID:" in response.json()["detail"] or "No se ha encontrado el jugador" in response.json()["detail"]

    app.dependency_overrides.clear()


@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_abandonar_sin_pertenecer(mock_JugadorService, mock_PartidaService, session):
    """
    Test de abandono de partida cuando el jugador no pertenece a la partida indicada
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # Crear un mock de la partida y jugadores
    partida_mock = MagicMock(id=1, anfitrionId=1, iniciada=False)  # Partida no iniciada
    
    jugador_no_pertenece = MagicMock(id=3, nombre="Jugador No Pertenece", partida_id=2)  # Jugador no pertenece a la partida

    # Configuración de los mocks
    mock_JugadorService.return_value = MagicMock(obtener_jugador=MagicMock(return_value=jugador_no_pertenece))
    mock_PartidaService.return_value = MagicMock(obtener_por_id=MagicMock(return_value=partida_mock))

    # Intentar abandonar una partida en la que el jugador no pertenece
    response = client.post(f"/partidas/{1}/abandonar?id_jugador=3")  # ID de jugador que no pertenece a la partida

    # Verificaciones
    assert response.status_code == 400  # Debería devolver error 400
    assert "El jugador no pertenece a la partida indicada" in response.json()["detail"]

    app.dependency_overrides.clear()


@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_abandonar_partida_anfitrion(mock_JugadorService, mock_PartidaService, session):
    """
    Test de abandono por parte del anfitrión, debería eliminar la partida y a los jugadores
    """
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    # Crear un mock de la partida con 2 jugadores (anfitrión y un invitado)
    partida_mock = MagicMock(id=1, anfitrionId=1, iniciada=False)  # La partida no está iniciada
    
    jugador_anfitrion = MagicMock(id=1, nombre="Anfitrión", partida_id=1)
    jugador_invitado = MagicMock(id=2, nombre="Jugador Invitado", partida_id=1)

    # Simular la lista de jugadores en la partida
    partida_mock.jugadores = [jugador_anfitrion, jugador_invitado]

    # Configuración de los mocks
    mock_JugadorService.return_value = MagicMock(obtener_jugador=MagicMock(return_value=jugador_anfitrion))
    mock_PartidaService.return_value = MagicMock(obtener_por_id=MagicMock(return_value=partida_mock))

    # Simulamos que `eliminar_partida` se llame cuando el anfitrión abandone
    mock_PartidaService.return_value.eliminar_partida = MagicMock()

    # Realizar el request
    response = client.post(f"/partidas/{1}/abandonar?id_jugador=1")

    # Verificaciones
    assert response.status_code == 200  # Debería devolver éxito
    assert response.json() == {"rol": "anfitrion"}  # El retorno debería indicar que el anfitrión abandonó

    # Verificar que la partida fue eliminada
    mock_PartidaService.return_value.eliminar_partida.assert_called_once_with(partida_mock)

    # NO se debe llamar a actualizar_cant_jugadores porque la partida se elimina directamente
    mock_PartidaService.return_value.actualizar_cant_jugadores.assert_not_called()

    app.dependency_overrides.clear()