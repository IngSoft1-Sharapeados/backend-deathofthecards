"""Modelo Jugador"""

from sqlalchemy import Column, Integer, String, Table, ForeignKey, Date, Boolean
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.orm import Mapped
from game.modelos.db import Base
from datetime import date
from typing import List

 
class Jugador(Base):
    __tablename__ = "jugadores"
 
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    desgracia_social: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
 
    # Relación de 1 a muchos con Carta
    cartas: Mapped[List["Carta"]] = relationship("Carta", back_populates="jugador", cascade="all, delete-orphan")
 
    # Relación de muchos a 1 con Partida
    partida_id: Mapped[int] = mapped_column(Integer, ForeignKey("partidas.id"))
    partida: Mapped["Partida"] = relationship("Partida", back_populates="jugadores")

