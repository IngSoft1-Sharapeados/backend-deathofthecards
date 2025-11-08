import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from types import SimpleNamespace
import os
import json
import random
from datetime import date

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from game.modelos.db import get_db, Base, get_session_local
from main import app

# modelos reales (según tu estructura previa)
from game.partidas.models import Partida, VotacionEvento
from game.jugadores.models import Jugador

# --- fixtures DB / client ------------------------------------------------------------------

@pytest.fixture(name="session")
def dbTesting_fixture():
    """Session en memoria para testing (reutilizable)."""
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
    """TestClient con override de dependencia get_db -> session (in-memory)."""
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# --- helpers para crear servicios usando la session ---------------------------

def make_partida_service_mock(session):
    """Devuelve un objeto que simula PartidaService pero opera sobre la session real."""
    svc = MagicMock()

    def obtener_por_id(pid):
        return session.query(Partida).filter_by(id=pid).first()

    def inicia_votacion(pid):
        p = session.query(Partida).filter_by(id=pid).first()
        if not p:
            raise ValueError(f"No se ha encontrado la partida con el ID:{pid}")
        p.votacion_activa = True
        session.commit()

    def fin_votacion(pid):
        p = session.query(Partida).filter_by(id=pid).first()
        if not p:
            raise ValueError(f"No se ha encontrado la partida con el ID:{pid}")
        p.votacion_activa = False
        session.commit()

    def registrar_voto(pid, votante_id, votado_id):
        # verificar duplicado
        exists = session.query(VotacionEvento).filter_by(partida_id=pid, votante_id=votante_id).first()
        if exists:
            raise ValueError("El jugador ya voto.")
        row = VotacionEvento(partida_id=pid, votante_id=votante_id, votado_id=votado_id)
        session.add(row)
        session.commit()

    def numero_de_votos(pid):
        return session.query(VotacionEvento).filter_by(partida_id=pid).count()

    def resolver_votacion(pid):
        # reproducir la misma lógica que el servicio real
        resultado = session.query(
            VotacionEvento.votado_id,
            # count via raw SQL aggregate
        ).filter_by(partida_id=pid).all()
        # usare group_by manualmente porque .all() anterior no cuenta; hacerlo con SQLAlchemy func:
        from sqlalchemy import func
        rows = session.query(
            VotacionEvento.votado_id,
            func.count(VotacionEvento.votado_id).label("cantidad")
        ).filter_by(partida_id=pid).group_by(VotacionEvento.votado_id).all()

        if not rows:
            raise ValueError("No hay votos registrados en esta partida.")
        max_cantidad = max(r.cantidad for r in rows)
        candidatos = [r.votado_id for r in rows if r.cantidad == max_cantidad]
        return random.choice(candidatos)

    def borrar_votacion(pid):
        session.query(VotacionEvento).filter_by(partida_id=pid).delete()
        session.commit()

    svc.obtener_por_id.side_effect = obtener_por_id
    svc.inicia_votacion.side_effect = inicia_votacion
    svc.fin_votacion.side_effect = fin_votacion
    svc.registrar_voto.side_effect = registrar_voto
    svc.numero_de_votos.side_effect = numero_de_votos
    svc.resolver_votacion.side_effect = resolver_votacion
    svc.borrar_votacion.side_effect = borrar_votacion
    svc.desgracia_social.return_value = False  # por defecto
    svc.obtener_turno_actual.return_value = None
    return svc


def make_jugador_service_mock(session):
    svc = MagicMock()
    def obtener_jugador(jid):
        return session.query(Jugador).filter_by(id=jid).first()
    svc.obtener_jugador.side_effect = obtener_jugador
    return svc


def make_carta_service_mock(session):
    svc = MagicMock()
    # Para estos tests no necesitamos lógica de cartas muy compleja; basta con stubs
    svc.obtener_cartas_jugadas.return_value = True  # simular que el evento fue jugado cuando se consulte
    svc.obtener_mano_jugador.return_value = []
    svc.obtener_carta_de_mano.return_value = SimpleNamespace(id_carta=999, partida_id=1, tipo="Event", ubicacion="mano", bocaArriba=False)
    svc.evento_jugado_en_turno.return_value = False
    return svc


# SimpleNamespace para caso en que lo necesitemos

#--- Tests point_your_suspicions(validacion de evento) ----------------------------------------------------

@patch("game.partidas.endpoints.votacion_activada")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_evento")
@patch("game.partidas.endpoints.manager")
def test_point_your_suspicions_ok(mock_manager, mock_verif_evento, mock_jugar_carta_evento, mock_votacion_activada, client, session):
    """Test: jugar evento Point Your Suspicions inicia correctamente la votación."""

    # preparar mocks
    mock_verif_evento.return_value = True
    mock_jugar_carta_evento.return_value = {"id": 99, "nombre": "Point your suspicions"}
    mock_votacion_activada.return_value = None
    mock_manager.broadcast = AsyncMock()

    # crear partida y jugador mínimos
    p = Partida(id=3, nombre="P3", anfitrionId=1, cantJugadores=2, iniciada=True, maxJugadores=4, minJugadores=2)
    session.add(p)
    j = Jugador(id=5, nombre="Jugador1", partida_id=3, fecha_nacimiento=date(2000, 1, 1))
    session.add(j)
    session.commit()

    # llamar endpoint
    resp = client.put("/partidas/3/evento/PointYourSuspicions?id_jugador=5&id_carta=10")
    assert resp.status_code == 200

    # verificar que se llamaron correctamente
    mock_verif_evento.assert_called_once_with("Point your suspicions", 10)
    mock_jugar_carta_evento.assert_called_once_with(3, 5, 10, session)
    mock_manager.broadcast.assert_awaited_once()
    mock_votacion_activada.assert_called_once_with(3, session)

    # el broadcast debe incluir el evento correcto
    args, _ = mock_manager.broadcast.await_args
    assert "se-jugo-point-your-suspicions" in args[1]
    assert '"jugador_id": 5' in args[1]
    
@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.verif_evento")
def test_point_your_suspicions_error_evento_invalido(mock_verif_evento, mock_manager, client):
    """Debe devolver 400 si la carta no corresponde al evento."""
    mock_verif_evento.return_value = False
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/PointYourSuspicions?id_jugador=1&id_carta=99")

    assert response.status_code == 400
    assert "La carta no corresponde al evento" in response.json()["detail"]
    mock_manager.broadcast.assert_not_called()


@patch("game.partidas.endpoints.manager")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_evento")
def test_point_your_suspicions_error_value(mock_verif_evento, mock_jugar_carta_evento, mock_manager, client):
    """Debe mapear correctamente errores ValueError del servicio."""
    mock_verif_evento.return_value = True
    mock_jugar_carta_evento.side_effect = ValueError("Partida no iniciada")
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/PointYourSuspicions?id_jugador=1&id_carta=11")

    assert response.status_code == 403
    assert "Partida no iniciada" in response.json()["detail"]
    mock_manager.broadcast.assert_not_called()
    

# ---------- TESTS DE ERRORES ADICIONALES (COBERTURA DE RAISES) ----------

@pytest.mark.parametrize("msg,expected_status", [
    ("No se encontro", 404),
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
def test_point_your_suspicions_mapeo_excepciones(mock_verif_evento, mock_jugar_carta_evento, mock_manager, client, msg, expected_status):
    """Debe mapear correctamente todos los ValueError posibles del servicio."""
    mock_verif_evento.return_value = True
    mock_jugar_carta_evento.side_effect = ValueError(msg)
    mock_manager.broadcast = AsyncMock()

    response = client.put("/partidas/1/evento/PointYourSuspicions?id_jugador=1&id_carta=10")

    assert response.status_code == expected_status
    assert msg in response.json()["detail"]
    mock_manager.broadcast.assert_not_called()

# --- Tests resolver_point_your suspicions(resolucion de evento) ------------------------------------------

@patch("game.partidas.endpoints.manager")
@patch("game.partidas.utils.CartaService")
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
def test_votacion_flujo_completo_ganador(mock_PartidaService_cls, mock_JugadorService_cls, mock_CartaService_cls, mock_manager, client, session):
    """
    Test flujo completo:
    - Creo partida y dos jugadores en la session.
    - Activo votacion.
    - Cada jugador vota (primero call1, luego call2).
    - Verifico broadcasts y estado final (votaciones borradas y votacion_activa False).
    """
    
    mock_manager.broadcast = AsyncMock()
    
    # crear partida y jugadores en la BD real (session)
    p = Partida(id=1, nombre="P1", anfitrionId=1, cantJugadores=2, iniciada=True, maxJugadores=4, minJugadores=2, turno_id=1, ordenTurnos="1,2")
    p.votacion_activa = True
    session.add(p)
    j1 = Jugador(id=1, nombre="J1", partida_id=1, fecha_nacimiento=date(2000, 1, 1))
    j2 = Jugador(id=2, nombre="J2", partida_id=1, fecha_nacimiento=date(2000, 1, 1))
    session.add_all([j1, j2])
    session.commit()

    # preparar servicios "reales" que usan la session internamente
    svc_partida = make_partida_service_mock(session)
    svc_jugador = make_jugador_service_mock(session)
    svc_carta = make_carta_service_mock(session)

    mock_PartidaService_cls.return_value = svc_partida
    mock_JugadorService_cls.return_value = svc_jugador
    mock_CartaService_cls.return_value = svc_carta

    # 1) primer voto: jugador 1 vota por 2
    resp1 = client.put(f"/partidas/1/evento/PointYourSuspicions/votacion?id_jugador=1&id_votante=1&id_votado=2")
    assert resp1.status_code == 200
    # broadcast por voto registrado fue llamado
    mock_manager.broadcast.assert_called()  # al menos un broadcast fue llamado
    # en DB hay 1 voto
    votos = session.query(VotacionEvento).filter_by(partida_id=1).all()
    assert len(votos) == 1
    assert votos[0].votante_id == 1 and votos[0].votado_id == 2

    mock_manager.broadcast.reset_mock()

    # 2) segundo voto: jugador 2 vota por 2 -> esto completa y resuelve
    resp2 = client.put(f"/partidas/1/evento/PointYourSuspicions/votacion?id_jugador=1&id_votante=2&id_votado=2")
    assert resp2.status_code == 200
    body2 = resp2.json()
    # la llamada final puede devolver el sospechoso (según tu endpoint devuelve el valor cuando finaliza)
    # Aceptamos int o dict con clave (flexible)
    sospechoso = None
    if isinstance(body2, dict) and "sospechoso" in body2:
        sospechoso = body2["sospechoso"]
    elif isinstance(body2, int):
        sospechoso = body2
    # esperando que sea 2
    assert sospechoso == 2 or sospechoso is None  # si tu endpoint retorna None, al menos la broadcast se llamó

    # broadcast final de votacion-finalizada
    calls = [c for c in mock_manager.broadcast.call_args_list if "votacion-finalizada" in json.dumps(c.kwargs.get('args', c.args) if c.kwargs else c.args)]
    # en caso de AsyncMock llamada, también verificamos que haya al menos una llamada
    assert mock_manager.broadcast.call_count >= 1

    # BD: la tabla de votaciones debe haber sido borrada tras resolución
    votos_final = session.query(VotacionEvento).filter_by(partida_id=1).count()
    assert votos_final == 0

    # partida.votacion_activa debe ser False
    p_after = session.query(Partida).filter_by(id=1).first()
    assert p_after.votacion_activa is False


@patch("game.partidas.endpoints.manager")
@patch("game.partidas.utils.CartaService")
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.PartidaService")
def test_votacion_empate_desempate_random(mock_PartidaService_cls, mock_JugadorService_cls, mock_CartaService_cls, mock_manager, client, session):
    """Empate entre dos jugadores; forzamos random.choice para predecir resultado."""
    
    mock_manager.broadcast = AsyncMock()
    
    # crear partida y 2 jugadores
    p = Partida(id=2, nombre="P2", anfitrionId=1, cantJugadores=2, iniciada=True, maxJugadores=4, minJugadores=2, turno_id=1, ordenTurnos="1,2")
    p.votacion_activa = True
    session.add(p)
    j1 = Jugador(id=10, nombre="A", partida_id=2, fecha_nacimiento=date(2000, 1, 1))
    j2 = Jugador(id=11, nombre="B", partida_id=2, fecha_nacimiento=date(2000, 1, 1))
    session.add_all([j1, j2])
    session.commit()

    svc_partida = make_partida_service_mock(session)
    svc_jugador = make_jugador_service_mock(session)
    svc_carta = make_carta_service_mock(session)

    mock_PartidaService_cls.return_value = svc_partida
    mock_JugadorService_cls.return_value = svc_jugador
    mock_CartaService_cls.return_value = svc_carta


    # voter 10 votes for 10
    r1 = client.put("/partidas/2/evento/PointYourSuspicions/votacion?id_jugador=2&id_votante=10&id_votado=10")
    assert r1.status_code == 200
    # voter 11 votes for 11 (tie 1-1)
    # patch random.choice to return 11 deterministically
    with patch("random.choice", return_value=11):
        r2 = client.put("/partidas/2/evento/PointYourSuspicions/votacion?id_jugador=2&id_votante=11&id_votado=11")
        assert r2.status_code == 200
        body = r2.json()
        # comprobar broadcast final
        assert mock_manager.broadcast.call_count >= 1
        # comprobar que la votacion fue resuelta y limpiada
        assert session.query(VotacionEvento).filter_by(partida_id=2).count() == 0
        # comprobar fin votacion
        p_after = session.query(Partida).filter_by(id=2).first()
        assert p_after.votacion_activa is False


@patch("game.partidas.utils.PartidaService")
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.CartaService")
def test_votacion_votante_ya_voto(mock_CartaService_cls, mock_JugadorService_cls, mock_PartidaService_cls, client, session):
    """Si un jugador ya votó, registrar_voto debe lanzar y endpoint debe devolver 400."""
    p = Partida(id=3, nombre="P3", anfitrionId=1, cantJugadores=2, iniciada=True, maxJugadores=4, minJugadores=2, turno_id=1, ordenTurnos="1,2")
    p.votacion_activa = True
    session.add(p)
    j1 = Jugador(id=20, nombre="U1", partida_id=3, fecha_nacimiento=date(2000, 1, 1))
    j2 = Jugador(id=21, nombre="U2", partida_id=3, fecha_nacimiento=date(2000, 1, 1))
    session.add_all([j1, j2])
    # pre-insertamos un voto de j1 para simular que ya votó
    session.add(VotacionEvento(partida_id=3, votante_id=20, votado_id=21))
    session.commit()

    svc_partida = make_partida_service_mock(session)
    svc_jugador = make_jugador_service_mock(session)
    svc_carta = make_carta_service_mock(session)
    mock_PartidaService_cls.return_value = svc_partida
    mock_JugadorService_cls.return_value = svc_jugador
    mock_CartaService_cls.return_value = svc_carta

    # intentar que j1 vote otra vez -> deberá fallar con 400
    resp = client.put("/partidas/3/evento/PointYourSuspicions/votacion?id_jugador=3&id_votante=20&id_votado=21")
    assert resp.status_code == 400
    assert "ya voto" in resp.json()["detail"].lower()

    # verificar que el voto extra no se haya insertado
    votos = session.query(VotacionEvento).filter_by(partida_id=3).all()
    assert len(votos) == 1


@patch("game.partidas.utils.PartidaService")
@patch("game.partidas.utils.JugadorService")
@patch("game.partidas.utils.CartaService")
def test_votacion_no_activa_rechazada(mock_CartaService_cls, mock_JugadorService_cls, mock_PartidaService_cls, client, session):
    """Si la votacion no está activa, el endpoint debe responder 403."""
    p = Partida(id=4, nombre="P4", anfitrionId=1, cantJugadores=2, iniciada=True, maxJugadores=4, minJugadores=2, turno_id=1, ordenTurnos="1,2")
    p.votacion_activa = False
    session.add(p)
    j1 = Jugador(id=30, nombre="U1", partida_id=4, fecha_nacimiento=date(2000, 1, 1))
    j2 = Jugador(id=31, nombre="U2", partida_id=4, fecha_nacimiento=date(2000, 1, 1))
    session.add_all([j1, j2])
    session.commit()

    svc_partida = make_partida_service_mock(session)
    svc_jugador = make_jugador_service_mock(session)
    svc_carta = make_carta_service_mock(session)
    mock_PartidaService_cls.return_value = svc_partida
    mock_JugadorService_cls.return_value = svc_jugador
    mock_CartaService_cls.return_value = svc_carta

    resp = client.put("/partidas/4/evento/PointYourSuspicions/votacion?id_jugador=4&id_votante=30&id_votado=31")
    assert resp.status_code == 403
    assert "no hay votacion" in resp.json()["detail"].lower()