from fastapi import FastAPI
import logging
from fastapi.middleware.cors import CORSMiddleware
from game.modelos.db import Base, get_engine

from api import api_router
#import os

app = FastAPI()

# Basic logging configuration for backend console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

#if os.path.exists("game.db"):
 #   os.remove("game.db")
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"]
)

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message":"HOLA"}

Base.metadata.create_all(bind=get_engine())
