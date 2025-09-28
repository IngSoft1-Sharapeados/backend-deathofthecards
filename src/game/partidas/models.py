"""Modelo Partida"""
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import List
from game.modelos.db import Base
 
class Partida(Base):
    __tablename__ = "partidas"
 
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    anfitrionId: Mapped[int] = mapped_column(Integer, nullable=False)
    cantJugadores: Mapped[int] = mapped_column(Integer, nullable=False)
    iniciada: Mapped[bool] = mapped_column(Boolean, default=False)
    maxJugadores: Mapped[int] = mapped_column(Integer, nullable=True)
    minJugadores: Mapped[int] = mapped_column(Integer, nullable=True)

    # Relación de 1 a muchos con Jugador
    jugadores: Mapped[List["Jugador"]] = relationship("Jugador", back_populates="partida")

    # relacion 1 a muchos con Carta
    cartas: Mapped[List["Carta"]] = relationship("Carta", back_populates="partida", cascade="all, delete-orphan")