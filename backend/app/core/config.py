import os
from typing import List

SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-32-random-bytes")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./mia.db")

_cors_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:4173",
)
CORS_ORIGINS: List[str] = [o.strip() for o in _cors_env.split(",") if o.strip()]
