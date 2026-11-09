from fastapi import APIRouter

from app.api.v1 import auth, employees, health, reference, rosters

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(reference.router)
api_router.include_router(rosters.router)
