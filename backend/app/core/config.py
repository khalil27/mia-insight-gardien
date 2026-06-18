import os
from typing import List

SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-32-random-bytes")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./mia.db")

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

_cors_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:4173,http://localhost:8081",
)
CORS_ORIGINS: List[str] = [o.strip() for o in _cors_env.split(",") if o.strip()]

# Max file sizes for uploads (bytes)
MAX_MODEL_SIZE:   int = 200 * 1024 * 1024   # 200 MB
MAX_DATASET_SIZE: int = 100 * 1024 * 1024   # 100 MB
