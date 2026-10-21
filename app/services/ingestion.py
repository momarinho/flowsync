import hmac
import hashlib
import json
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from app.core.config import settings
from app.models.staging import StagingEvent
from app.models.core import CoreShipment, CoreShipmentEvent
from app.models.quarantine import QuarantineEvent
from app.schemas.comex import ComexWebhookInput


def verify_hmac_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Valida a assinatura HMAC SHA-256 recebida no header do Webhook.
    Se nenhuma assinatura for enviada em ambiente de teste/dev, permite se configurado,
    mas em produção rejeita requisições não assinadas.
    """
    if not signature_header:
        return False
    
    expected_signature = hmac.new(
        key=settings.WEBHOOK_SECRET.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    # hmac.compare_digest evita ataques de temporização (timing attacks)
    return hmac.compare_digest(expected_signature, signature_header)


def generate_event_idempotency_hash(tracking_number: str, event_code: str, occurred_at: str) -> str:
    """
    Gera um hash SHA-256 único para eventos de rastreamento de navio/porto,
    evitando que o mesmo evento seja gravado duas vezes por oscilação de rede.
    """
    content = f"{tracking_number}:{event_code}:{occurred_at}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def ingest_raw_webhook(
    db: Session,
    provider: str,
    raw_payload: Dict[str, Any],
    signature: Optional[str] = None
) -> StagingEvent:
    """
    Passo 1 da Ingestão: Grava o payload bruto na Camada 1 (Staging) em altíssima velocidade.
    Retorna o registro para posterior processamento assíncrono.
    """
    event_id = raw_payload.get("event_id", "UNKNOWN_EVENT")
    staging_event = StagingEvent(
        event_id=event_id,
        provider=provider.upper(),
        raw_payload=raw_payload,
        signature=signature,
        status="PENDING"
    )
    db.add(staging_event)
    db.commit()
    db.refresh(staging_event)
    return staging_event


def process_staging_event(db: Session, staging_event_id: str) -> Tuple[str, Optional[str]]:
    """
    Passo 2 do Pipeline: Valida o contrato e despacha para Core ou Quarentena.
    Retorna (status_final, id_gerado)
    """
    staging_event = db.query(StagingEvent).filter(StagingEvent.id == staging_event_id).first()
    if not staging_event:
        return ("NOT_FOUND", None)

    try:
        # 1. Validação de Contrato Canônico Comex (Pydantic v2)
        valid_input = ComexWebhookInput(**staging_event.raw_payload)
        shipment_data = valid_input.shipment

        # 2. Inserção / Upsert no Core (Camada 2 - ACID)
        existing_shipment = db.query(CoreShipment).filter(
            CoreShipment.tracking_number == shipment_data.tracking_number
        ).first()

        if existing_shipment:
            # Atualiza status e campos dinâmicos
            existing_shipment.current_status = shipment_data.status
            existing_shipment.declared_value = shipment_data.declared_value
            existing_shipment.currency = shipment_data.currency
            target_shipment = existing_shipment
        else:
            # Cria novo registro consolidado
            target_shipment = CoreShipment(
                tracking_number=shipment_data.tracking_number,
                bill_of_lading=shipment_data.bill_of_lading,
                container_number=shipment_data.container_number,
                origin_port=shipment_data.origin_port,
                destination_port=shipment_data.destination_port,
                incoterm=shipment_data.incoterm,
                declared_value=shipment_data.declared_value,
                currency=shipment_data.currency,
                current_status=shipment_data.status
            )
            db.add(target_shipment)

        # 3. Atualiza status no Staging para PROCESSED
        staging_event.status = "PROCESSED"
        db.commit()
        db.refresh(target_shipment)
        return ("PROCESSED", str(target_shipment.id))

    except ValidationError as val_err:
        # Falha de contrato! Isola na Quarentena (Camada 3) sem quebrar o pipeline
        db.rollback()
        serialized_errors = json.loads(val_err.json())
        quarantine_entry = QuarantineEvent(
            staging_event_id=staging_event.id,
            provider=staging_event.provider,
            raw_payload=staging_event.raw_payload,
            rejection_reason="CONTRACT_VALIDATION_FAILED",
            validation_errors=serialized_errors
        )
        db.add(quarantine_entry)

        # Atualiza o staging para QUARANTINED
        staging_event = db.query(StagingEvent).filter(StagingEvent.id == staging_event_id).first()
        if staging_event:
            staging_event.status = "QUARANTINED"

        db.commit()
        db.refresh(quarantine_entry)
        return ("QUARANTINED", str(quarantine_entry.id))

    except Exception as err:
        db.rollback()
        quarantine_entry = QuarantineEvent(
            staging_event_id=staging_event.id,
            provider=staging_event.provider,
            raw_payload=staging_event.raw_payload,
            rejection_reason=f"SYSTEM_ERROR: {type(err).__name__}",
            validation_errors={"error": str(err)}
        )
        db.add(quarantine_entry)
        staging_event = db.query(StagingEvent).filter(StagingEvent.id == staging_event_id).first()
        if staging_event:
            staging_event.status = "QUARANTINED"
        db.commit()
        return ("ERROR_QUARANTINED", str(quarantine_entry.id))
