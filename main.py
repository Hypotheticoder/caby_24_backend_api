from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
from database import engine, Base
from routes.users import router as users_router
from routes.customer_orders import router as customer_orders_router
from routes.payments import router as payments_router
from routes.admin_earnings import router as admin_earnings_router
from routes.auth import router as auth_router
from routes.delivery import router as delivery_router
from routes.webhooks import router as webhooks_router
from routes.drivers import router as drivers_router
from routes import global_timing

logging.basicConfig(level=logging.INFO)

# Avoid logging full request URLs (which may contain secrets like API keys).
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("parcel-backend")

app = FastAPI(title="Parcel Backend")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.include_router(users_router)
app.include_router(customer_orders_router)
app.include_router(payments_router)
app.include_router(admin_earnings_router)
app.include_router(auth_router)
app.include_router(delivery_router)
app.include_router(webhooks_router)
app.include_router(drivers_router)
app.include_router(global_timing.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
def read_root():
	return {"message": "Backend started: FastAPI app is up"}


@app.on_event("startup")
def on_startup():
	# Create tables for development; use Alembic for migrations in production
	Base.metadata.create_all(bind=engine)
	logger.info("Backend started: FastAPI app is up (development mode)")
