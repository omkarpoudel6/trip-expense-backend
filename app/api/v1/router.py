from fastapi import APIRouter

from app.api.v1 import auth

api_router = APIRouter()
api_router.include_router(auth.router)

# Future milestones register their routers here, e.g.:
# from app.api.v1 import trips
# api_router.include_router(trips.router)