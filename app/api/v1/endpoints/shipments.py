from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.models.core import CoreShipment

router = APIRouter()


@router.get("", summary="Listar Embarques Marítimos Consolidados (Core)")
def list_shipments(
    status: Optional[str] = Query(None, description="Filtrar por status (ex: IN_TRANSIT, DELIVERED)"),
    container: Optional[str] = Query(None, description="Filtrar por número de contêiner ISO 6346"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Camada 2 (Core):
    Exibe os dados canônicos consolidados após validação e garantia ACID.
    """
    query = db.query(CoreShipment)
    
    if status:
        query = query.filter(CoreShipment.current_status == status.upper())
    if container:
        query = query.filter(CoreShipment.container_number == container.upper())
        
    shipments = query.order_by(CoreShipment.created_at.desc()).limit(limit).all()
    
    return [
        {
            "id": str(s.id),
            "tracking_number": s.tracking_number,
            "bill_of_lading": s.bill_of_lading,
            "container_number": s.container_number,
            "origin_port": s.origin_port,
            "destination_port": s.destination_port,
            "incoterm": s.incoterm,
            "declared_value": float(s.declared_value),
            "currency": s.currency,
            "current_status": s.current_status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None
        }
        for s in shipments
    ]


@router.get("/{tracking_number}", summary="Detalhes de um Embarque por Tracking Number")
def get_shipment_by_tracking(tracking_number: str, db: Session = Depends(get_db)):
    shipment = db.query(CoreShipment).filter(
        CoreShipment.tracking_number == tracking_number
    ).first()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embarque com tracking '{tracking_number}' não encontrado."
        )
        
    return {
        "id": str(shipment.id),
        "tracking_number": shipment.tracking_number,
        "bill_of_lading": shipment.bill_of_lading,
        "container_number": shipment.container_number,
        "origin_port": shipment.origin_port,
        "destination_port": shipment.destination_port,
        "incoterm": shipment.incoterm,
        "declared_value": float(shipment.declared_value),
        "currency": shipment.currency,
        "current_status": shipment.current_status,
        "created_at": shipment.created_at.isoformat() if shipment.created_at else None,
        "events": [
            {
                "id": str(e.id),
                "event_code": e.event_code,
                "description": e.description,
                "location": e.location,
                "occurred_at": e.occurred_at.isoformat(),
                "idempotency_hash": e.idempotency_hash
            }
            for e in shipment.events
        ]
    }
