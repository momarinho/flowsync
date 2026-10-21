from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter()


@router.get("", summary="Métricas Consolidadas de Integração (BI / Observabilidade)")
def get_integration_metrics(db: Session = Depends(get_db)):
    """
    Consulta em tempo real a View SQL 'v_integration_metrics' do PostgreSQL:
    - Total de webhooks ingeridos (Staging)
    - Total processado com sucesso (Core)
    - Total isolado por quebra de contrato (Quarentena)
    - Taxa de sucesso percentual
    """
    result = db.execute(text("SELECT * FROM v_integration_metrics")).mappings().first()
    
    if not result:
        return {
            "total_ingested": 0,
            "total_processed": 0,
            "total_quarantined": 0,
            "success_rate_percentage": 0.0
        }
        
    return {
        "total_ingested": int(result["total_ingested"] or 0),
        "total_processed": int(result["total_processed"] or 0),
        "total_quarantined": int(result["total_quarantined"] or 0),
        "success_rate_percentage": float(result["success_rate_percentage"] or 0.0)
    }
