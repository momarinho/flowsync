import json
from fastapi import APIRouter, Depends, Header, HTTPException, Request, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db, SessionLocal
from app.services.ingestion import (
    verify_hmac_signature,
    ingest_raw_webhook,
    process_staging_event
)

router = APIRouter()


def run_background_pipeline(staging_event_id: str):
    """
    Worker em background executado de forma assíncrona após o webhook responder 200 OK.
    Abre uma sessão de banco independente para a thread em background.
    """
    db = SessionLocal()
    try:
        process_staging_event(db, staging_event_id)
    finally:
        db.close()


@router.post("/comex", status_code=status.HTTP_202_ACCEPTED, summary="Ingestão de Webhooks Comex")
async def receive_comex_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_flowls_signature: Optional[str] = Header(None, alias="X-Flowls-Signature")
):
    """
    Endpoint de Ingestão de Webhooks em Alta Performance:
    1. Lê o payload bruto em bytes.
    2. Valida a assinatura HMAC (se fornecida).
    3. Persiste o dado bruto na Camada 1 (Staging) imediatamente.
    4. Devolve HTTP 202 Accepted em menos de 50ms.
    5. Despacha o processamento de regras e quarentena para background tasks.
    """
    raw_body = await request.body()
    
    # Se a assinatura for fornecida, validamos o HMAC
    if x_flowls_signature:
        if not verify_hmac_signature(raw_body, x_flowls_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Assinatura HMAC inválida. Rejeitado por segurança na borda."
            )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload inválido: esperado formato JSON."
        )

    provider = payload.get("provider", "UNKNOWN")

    # Ingestão em Staging (Auditoria Rápida)
    staging_event = ingest_raw_webhook(
        db=db,
        provider=provider,
        raw_payload=payload,
        signature=x_flowls_signature
    )

    # Agenda a validação de contrato e consolidação em background
    background_tasks.add_task(run_background_pipeline, str(staging_event.id))

    return {
        "status": "ACCEPTED",
        "staging_id": str(staging_event.id),
        "provider": provider,
        "message": "Webhook recebido com sucesso e agendado para processamento assíncrono."
    }


@router.post("/comex/sync", status_code=status.HTTP_200_OK, summary="Ingestão Síncrona (Para Testes e Validação)")
async def receive_comex_webhook_sync(
    request: Request,
    db: Session = Depends(get_db),
    x_flowls_signature: Optional[str] = Header(None, alias="X-Flowls-Signature")
):
    """
    Endpoint síncrono para fins de testes automatizados e demonstração em tempo real:
    Executa a ingestão e o processamento no mesmo ciclo de requisição.
    """
    raw_body = await request.body()
    
    if x_flowls_signature:
        if not verify_hmac_signature(raw_body, x_flowls_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Assinatura HMAC inválida."
            )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload inválido: esperado formato JSON."
        )

    provider = payload.get("provider", "UNKNOWN")

    staging_event = ingest_raw_webhook(
        db=db,
        provider=provider,
        raw_payload=payload,
        signature=x_flowls_signature
    )

    result_status, result_id = process_staging_event(db, str(staging_event.id))

    return {
        "status": result_status,
        "staging_id": str(staging_event.id),
        "result_id": result_id,
        "provider": provider
    }
