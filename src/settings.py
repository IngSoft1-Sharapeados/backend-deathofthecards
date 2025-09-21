import os

class Settings:
    # Base de datos de produccion
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///games.db")

    # Base de datos para testing (en memoria)
    TEST_DATABASE_URL: str = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

settings = Settings()