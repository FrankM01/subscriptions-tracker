from fastapi import FastAPI

from app.routers.subscriptions import router as subscriptions_router, set_service
from app.services.subscription_service import SubscriptionService
from app.store.subscription_store import SubscriptionStore

# Instantiate the data store and service layer
store = SubscriptionStore()
service = SubscriptionService(store)

# Wire the service into the router before the app starts handling requests
set_service(service)

app = FastAPI(title="Subscriptions Tracker", version="1.0.0")

app.include_router(subscriptions_router)
