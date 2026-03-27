from fastapi import FastAPI
import logging
from database import engine, Base
from routes.users import router as users_router
from routes.customer_orders import router as customer_orders_router
from routes.payments import router as payments_router
from routes.auth import router as auth_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("parcel-backend")

app = FastAPI(title="Parcel Backend")
app.include_router(users_router)
app.include_router(customer_orders_router)
app.include_router(payments_router)
app.include_router(auth_router)


@app.get("/", include_in_schema=False)
def read_root():
	return {"message": "Backend started: FastAPI app is up"}


@app.on_event("startup")
def on_startup():
	# Create tables for development; use Alembic for migrations in production
	Base.metadata.create_all(bind=engine)
	logger.info("Backend started: FastAPI app is up (development mode)")
