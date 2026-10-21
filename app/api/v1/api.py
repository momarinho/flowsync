from fastapi import APIRouter
from app.api.v1.endpoints import webhooks, quarantine, metrics, shipments

api_router = APIRouter()

api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks & Ingestão"])
api_router.include_router(shipments.router, prefix="/shipments", tags=["Core Comex"])
api_router.include_router(quarantine.router, prefix="/quarantine", tags=["Quarentena & Anomalias"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["Métricas & BI"])
