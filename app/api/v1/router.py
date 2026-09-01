from fastapi import APIRouter

from app.api.v1 import auth, trips, expenses, settlements, notification

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(trips.router)
api_router.include_router(expenses.router)
api_router.include_router(settlements.router)
api_router.include_router(notification.router)

# Future milestones register their routers here, e.g.:
# from app.api.v1 import trips
# api_router.include_router(trips.router)