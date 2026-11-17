from pathlib import Path

from fastapi import FastAPI
from app.frontend import mount_frontend

from app.routers.auth import router as auth_router
from app.routers.subscriptions import router as subscriptions_router, set_service
from app.services.subscription_service import SubscriptionService
from app.database import make_engine
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.utility_repository import UtilityRepository
from app.routers.utilities import router as utilities_router
from app.services.utility_service import UtilityService

# Use the configured PostgreSQL or SQLite database for all API operations.
engine = make_engine()
repository = SubscriptionRepository(engine)
service = SubscriptionService(repository)

# Wire the service into the router before the app starts handling requests
set_service(service)

app = FastAPI(title="Subscriptions Tracker", version="1.0.0")
app.state.utility_service = UtilityService(UtilityRepository(engine))

app.include_router(auth_router)
app.include_router(subscriptions_router)
app.include_router(utilities_router)

# The API stays usable during development before the frontend is built.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
mount_frontend(app, PROJECT_ROOT / "frontend" / "dist")
