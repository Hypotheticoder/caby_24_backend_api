import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# In development, automatically load variables from a local .env file if present.
if os.path.exists(".env"):
    load_dotenv(dotenv_path=".env")

# Read DB configuration from environment only. Do NOT set secrets in code.
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

missing = [k for k in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME") if not os.getenv(k)]
if missing:
    raise RuntimeError(
        "Missing required database environment variables: " + ", ".join(missing)
    )

SQLALCHEMY_DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Ensure Alembic loads all models.
from models.transaction import Transaction
from models.global_settings import GlobalSetting

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
