from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.models.quarantine import QuarantineEvent
from app.services.ingestion import process_staging_event

router = APIRouter()


@router.get("", summary="Listar Eventos em Quarentena")
def list_quarantine_events(
    resolved: Optional[bool] = Query(False, description="Filtrar por eventos resolvidos ou pendentes"),
    provider: Optional[str] = Query(None, description="Filtrar por armador/provedor (ex: MAERSK)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Camada 3 (Observabilidade & Quarentena):
    Permite que o time de suporte e integrações audite eventos que violaram
    contratos de Comex (contêiner fora do padrão ISO, portos desconhecidos, etc.).
    """
    query = db.query(QuarantineEvent)
    
    if resolved is not None:
        query = query.filter(QuarantineEvent.resolved == resolved)
    
    if provider:
        query = query.filter(QuarantineEvent.provider == provider.upper())
        
    events = query.order_by(QuarantineEvent.created_at.desc()).limit(limit).all()
    
    return [
        {
            "id": str(e.id),
            "staging_event_id": str(e.staging_event_id) if e.staging_event_id else None,
            "provider": e.provider,
            "rejection_reason": e.rejection_reason,
            "validation_errors": e.validation_errors,
            "raw_payload": e.raw_payload,
            "resolved": e.resolved,
            "created_at": e.created_at.isoformat() if e.created_at else None
        }
        for e in events
    ]


@router.post("/{quarantine_id}/resolve", summary="Marcar Quarentena como Resolvida")
def resolve_quarantine_event(
    quarantine_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Marca uma anomalia de quarentena como tratada após correção manual pelo time de operações.
    """
    entry = db.query(QuarantineEvent).filter(QuarantineEvent.id == quarantine_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de quarentena não encontrado."
        )
    
    entry.resolved = True
    db.commit()
    db.refresh(entry)
    
    return {
        "id": str(entry.id),
        "status": "RESOLVED",
        "message": "Registro de quarentena marcado como resolvido com sucesso."
    }
