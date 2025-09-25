from fastapi import APIRouter, Depends, HTTPException, status
from game.jugadores.models import Jugador
from game.jugadores.schemas import JugadorData, JugadorResponse
from game.jugadores.services import JugadorService
from game.modelos.db import get_db


jugadores_router = APIRouter()
