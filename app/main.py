from fastapi import FastAPI

from app.routers.subscriptions import router as subscriptions_router, set_service
from app.services.subscription_service import SubscriptionService
from app.database import make_engine
from app.repositories.subscription_repository import SubscriptionRepository

# Use the configured SQLite database for all API operations.
engine = make_engine()
repository = SubscriptionRepository(engine)
service = SubscriptionService(repository)

# Wire the service into the router before the app starts handling requests
set_service(service)

app = FastAPI(title="Subscriptions Tracker", version="1.0.0")

app.include_router(subscriptions_router)
