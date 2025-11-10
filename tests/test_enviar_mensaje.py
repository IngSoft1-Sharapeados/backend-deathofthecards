import pytest
from main import app
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from game.partidas.schemas import Mensaje
from game.partidas.utils import *
from game.modelos.db import get_db



# -------------------------------- Tests untarios ----------------------------------------------------------------------------

@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_enviar_mensaje_exitoso(MockJugadorService, MockPartidaService, mock_db, partida_iniciada, jugadorChat, mensaje):
    """Test de envío correcto del mensaje."""
    
    MockPartidaService.return_value.obtener_por_id.return_value = partida_iniciada
    MockJugadorService.return_value.obtener_jugador.return_value = jugadorChat

    resultado = enviar_mensaje(1, 1, mensaje, mock_db)

    assert resultado is True
    MockPartidaService.return_value.obtener_por_id.assert_called_once_with(1)
    MockJugadorService.return_value.obtener_jugador.assert_called_once_with(1)


@patch('game.partidas.utils.PartidaService')
def test_enviar_mensaje_partida_no_encontrada(MockPartidaService, mock_db, jugadorChat, mensaje):
    """Test de partida no encontrada."""

    MockPartidaService.return_value.obtener_por_id.return_value = None

    with pytest.raises(ValueError, match="No se ha encontrado la partida con el ID:999"):
        enviar_mensaje(999, 11, mensaje, mock_db)


@patch('game.partidas.utils.PartidaService')
def test_enviar_mensaje_partida_no_iniciada(MockPartidaService, mock_db, partida_iniciada, jugadorChat, mensaje):
    """Test para partida no iniciada."""

    partida_iniciada.iniciada = False
    MockPartidaService.return_value.obtener_por_id.return_value = partida_iniciada

    with pytest.raises(ValueError, match="Partida no iniciada"):
        enviar_mensaje(1, 101, mensaje, mock_db)


@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_enviar_mensaje_jugador_no_encontrado(MockJugadorService, MockPartidaService, mock_db, partida_iniciada, mensaje):
    """Test para jugador no encontrado."""

    MockPartidaService.return_value.obtener_por_id.return_value = partida_iniciada
    MockJugadorService.return_value.obtener_jugador.return_value = None

    with pytest.raises(ValueError, match="No se ha encontrado el jugador 999."):
        enviar_mensaje(1, 999, mensaje, mock_db)


@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_enviar_mensaje_jugador_no_pertenece_a_partida(MockJugadorService, MockPartidaService, mock_db, partida_iniciada, jugadorChat, mensaje):
    """Test jugador no pertenece a la partida."""

    MockPartidaService.return_value.obtener_por_id.return_value = partida_iniciada
    jugadorChat.partida_id = 2
    MockJugadorService.return_value.obtener_jugador.return_value = jugadorChat

    with pytest.raises(ValueError, match="no pertenece a la partida"):
        enviar_mensaje(1, 101, mensaje, mock_db)


@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_enviar_mensaje_demasiado_largo(MockJugadorService, MockPartidaService, mock_db, partida_iniciada, jugadorChat):
    """Test para mensaje de más de 200 caracteres."""

    MockPartidaService.return_value.obtener_por_id.return_value = partida_iniciada
    MockJugadorService.return_value.obtener_jugador.return_value = jugadorChat

    mensaje_largo = "A" * 201
    mensaje_largo = Mensaje(nombreJugador="Alice", texto=mensaje_largo)

    with pytest.raises(ValueError, match="Mensaje demasiado largo"):
        enviar_mensaje(1, 101, mensaje_largo, mock_db)


@patch('game.partidas.utils.PartidaService')
@patch('game.partidas.utils.JugadorService')
def test_enviar_mensaje_nombre_jugador_no_coincide(MockJugadorService, MockPartidaService, mock_db, partida_iniciada, jugadorChat):
    """Test para nombre en el payload que no coincide con el nombre del Jugador."""

    MockPartidaService.return_value.obtener_por_id.return_value = partida_iniciada
    MockJugadorService.return_value.obtener_jugador.return_value = jugadorChat # Nombre es "Alice"

    mensaje_otro_nombre = Mensaje(nombreJugador="Bob", texto="Hola!")

    with pytest.raises(ValueError, match="El nombre del jugador no coincide"):
        enviar_mensaje(1, 101, mensaje_otro_nombre, mock_db)




#------------------------------------------------ Test integración -----------------------------------------------------------------

def test_integracion_enviar_mensaje_ok(session):
    """ Test para envío de mensaje exitoso con base de datos de testing (RAM) """

    partida = Partida(
        id = 1,
        nombre = "PartidaChat",
        anfitrionId = 1,
        cantJugadores = 2,
        iniciada = True
    )

    jugador = Jugador(
        id = 1,
        nombre = "Fran",
        partida_id = 1,
        fecha_nacimiento = date(1990, 3, 3),  
        desgracia_social = False
    )
    session.add(partida)
    session.add(jugador)
    session.commit()

    def get_db_override():
        yield session
    
    app.dependency_overrides[get_db] = get_db_override

    client = TestClient(app)

    payload = {"nombreJugador": "Fran", "texto": "hola como andas"}
    response = client.post(f"/partidas/1/envio-mensaje?id_jugador=1", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"nombre": payload["nombreJugador"], "texto": payload["texto"]}


def test_error_partida_no_encontrada(db_partida_chat):
    """ Test para cuando la partida no existe """
    client = TestClient(app)
    payload = {"nombreJugador": "Fran", "texto": "hola como andas"}
    
    response = client.post(f"/partidas/999/envio-mensaje?id_jugador=1", json=payload)
    
    assert response.status_code == 404
    assert response.json() == {"detail": "No se ha encontrado la partida con el ID:999"}


def test_error_partida_no_iniciada(db_partida_chat):
    """ Test para cuando la partida no está iniciada """
    client = TestClient(app)
    payload = {"nombreJugador": "Fran", "texto": "hola como andas"}

    partida_iniciada = db_partida_chat.query(Partida).filter(Partida.id == 1).first()
    partida_iniciada.iniciada = False
    db_partida_chat.commit()

    response = client.post(f"/partidas/1/envio-mensaje?id_jugador=1", json=payload)
    
    assert response.status_code == 400
    assert response.json() == {"detail": "Partida no iniciada"}


def test_error_jugador_no_encontrado(db_partida_chat):
    """ Test para cuando el jugador no existe """
    client = TestClient(app)
    payload = {"nombreJugador": "Fran", "texto": "hola como andas"}

    response = client.post(f"/partidas/1/envio-mensaje?id_jugador=999", json=payload)
    
    assert response.status_code == 404
    assert response.json() == {"detail": "No se ha encontrado el jugador 999."}


def test_error_jugador_no_pertenece_a_partida(db_partida_chat):
    """ Test para cuando el jugador no pertenece a la partida """
    client = TestClient(app)
    payload = {"nombreJugador": "Fran", "texto": "hola como andas"}

    jugador = db_partida_chat.query(Jugador).filter(Jugador.id == 1).first()
    jugador.partida_id = 2
    db_partida_chat.commit()

    response = client.post(f"/partidas/1/envio-mensaje?id_jugador=1", json=payload)
    
    assert response.status_code == 403
    assert response.json() == {"detail": "El jugador con ID 1 no pertenece a la partida 1."}


def test_error_mensaje_demasiado_largo(db_partida_chat):
    """ Test para cuando el mensaje es demasiado largo """
    client = TestClient(app)
    mensaje_largo = "A" * 201
    payload = {"nombreJugador": "Fran", "texto": mensaje_largo}

    response = client.post(f"/partidas/1/envio-mensaje?id_jugador=1", json=payload)
    
    assert response.status_code == 413
    assert response.json() == {"detail": "Mensaje demasiado largo. No puede tener más de 200 caracteres"}


def test_error_nombre_jugador_no_coincide(db_partida_chat):
    """ Test para cuando el nombre del jugador no coincide con el nombre en el mensaje """
    client = TestClient(app)
    payload = {"nombreJugador": "Fran", "texto": "hola como andas"}

    payload["nombreJugador"] = "Juan"

    response = client.post(f"/partidas/1/envio-mensaje?id_jugador=1", json=payload)
    
    assert response.status_code == 400
    assert response.json() == {"detail": "El nombre del jugador no coincide con el nombre del mensaje"}
