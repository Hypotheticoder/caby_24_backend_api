from fastapi import FastAPI
import logging
from database import engine, Base
from routes.users import router as users_router
from routes.orders import router as orders_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("parcel-backend")

app = FastAPI(title="Parcel Backend")
app.include_router(users_router)
app.include_router(orders_router)


@app.get("/", include_in_schema=False)
def read_root():
	return {"message": "Backend started: FastAPI app is up"}


@app.on_event("startup")
def on_startup():
	# Create tables for development; use Alembic for migrations in production
	Base.metadata.create_all(bind=engine)
	logger.info("Backend started: FastAPI app is up (development mode)")
