import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def compute_signature(payload_dict: dict) -> str:
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    return hmac.new(
        key=settings.WEBHOOK_SECRET.encode("utf-8"),
        msg=raw_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["postgres"] == "connected"


def test_webhook_invalid_hmac_rejected():
    payload = {
        "event_id": "evt-fake-001",
        "provider": "MSC",
        "shipment": {
            "tracking_number": "TRK-FAKE",
            "bill_of_lading": "BL-FAKE",
            "container_number": "MSCU1234567",
            "origin_port": "BRSSZ",
            "destination_port": "CNSHA",
            "incoterm": "FOB",
            "declared_value": 50000.0,
            "currency": "USD"
        }
    }
    # Envia com assinatura forjada
    response = client.post(
        "/api/v1/webhooks/comex/sync",
        json=payload,
        headers={"X-Flowls-Signature": "assinatura_completamente_invalida"}
    )
    assert response.status_code == 401
    assert "Assinatura HMAC inválida" in response.json()["detail"]


def test_webhook_valid_payload_processed_to_core():
    tracking = "TRK-TEST-MAERSK-999"
    payload = {
        "event_id": "evt-maersk-real-001",
        "provider": "MAERSK",
        "shipment": {
            "tracking_number": tracking,
            "bill_of_lading": "MEDU8829102",
            "container_number": "MAEU7654321",  # ISO 6346 válido
            "origin_port": "BRSSZ",              # UN/LOCODE Santos válido
            "destination_port": "CNSHA",         # UN/LOCODE Xangai válido
            "incoterm": "FOB",
            "declared_value": 78500.00,
            "currency": "USD",
            "status": "IN_TRANSIT"
        }
    }
    
    # Computa assinatura legítima
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/v1/webhooks/comex/sync",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Flowls-Signature": sig
        }
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "PROCESSED"
    assert res["result_id"] is not None

    # Consulta no Core
    shipment_res = client.get(f"/api/v1/shipments/{tracking}")
    assert shipment_res.status_code == 200
    shipment = shipment_res.json()
    assert shipment["container_number"] == "MAEU7654321"
    assert shipment["origin_port"] == "BRSSZ"
    assert shipment["declared_value"] == 78500.00


def test_webhook_corrupted_payload_goes_to_quarantine_resiliently():
    """
    Cenário Crítico Comex: Armador envia número de contêiner corrompido.
    A API NÃO deve explodir com erro 500. Deve absorver o dado,
    isolar na quarentena e permitir auditoria.
    """
    tracking = "TRK-CORRUPTED-002"
    payload = {
        "event_id": "evt-bad-container-002",
        "provider": "HAPAG_LLOYD",
        "shipment": {
            "tracking_number": tracking,
            "bill_of_lading": "HLCU129381",
            "container_number": "CONTAINER_SUJO_SEM_FORMATO",  # Quebra ISO 6346!
            "origin_port": "BRSSZ",
            "destination_port": "CNSHA",
            "incoterm": "CIF",
            "declared_value": 30000.00,
            "currency": "USD",
            "status": "BOOKED"
        }
    }

    response = client.post(
        "/api/v1/webhooks/comex/sync",
        json=payload
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "QUARANTINED"
    quarantine_id = res["result_id"]
    assert quarantine_id is not None

    # Verifica se o Core foi preservado (NÃO deve ter inserido tracking sujo no Core)
    core_check = client.get(f"/api/v1/shipments/{tracking}")
    assert core_check.status_code == 404

    # Verifica se está na Quarentena com o log do erro
    quarantine_res = client.get("/api/v1/quarantine?resolved=false")
    assert quarantine_res.status_code == 200
    items = quarantine_res.json()
    matched = [item for item in items if item["id"] == quarantine_id]
    assert len(matched) == 1
    assert matched[0]["rejection_reason"] == "CONTRACT_VALIDATION_FAILED"
    assert "ISO 6346" in str(matched[0]["validation_errors"])


def test_integration_metrics_endpoint():
    """
    Testa se a View Analítica SQL 'v_integration_metrics' reflete os dados em tempo real.
    """
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert metrics["total_ingested"] >= 2
    assert metrics["total_processed"] >= 1
    assert metrics["total_quarantined"] >= 1
    assert 0.0 <= metrics["success_rate_percentage"] <= 100.0


def test_resolve_quarantine_item():
    """
    Testa a resolução de um item em quarentena pelo time de operações.
    """
    # 1. Busca itens não resolvidos
    res = client.get("/api/v1/quarantine?resolved=false")
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    target_id = items[0]["id"]

    # 2. Marca como resolvido
    resolve_res = client.post(f"/api/v1/quarantine/{target_id}/resolve")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"


def test_idempotent_duplicate_webhook_does_not_duplicate_shipment():
    """
    Garante que retransmissões do mesmo evento de frete atualizam o Core
    sem duplicar registros de remessa.
    """
    tracking = "TRK-IDEMPOTENT-001"
    payload = {
        "event_id": "evt-dup-001",
        "provider": "SANTOS_PORT",
        "shipment": {
            "tracking_number": tracking,
            "bill_of_lading": "BL-DUP-999",
            "container_number": "SSZX9876543",
            "origin_port": "BRSSZ",
            "destination_port": "CNSHA",
            "incoterm": "CIF",
            "declared_value": 12000.00,
            "currency": "USD",
            "status": "BOOKED"
        }
    }

    # Primeiro envio
    res1 = client.post("/api/v1/webhooks/comex/sync", json=payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "PROCESSED"

    # Segundo envio com status atualizado
    payload["shipment"]["status"] = "IN_TRANSIT"
    res2 = client.post("/api/v1/webhooks/comex/sync", json=payload)
    assert res2.status_code == 200
    assert res2.json()["status"] == "PROCESSED"

    # Confere no Core que há apenas 1 registro e o status foi atualizado
    shipment_res = client.get(f"/api/v1/shipments/{tracking}")
    assert shipment_res.status_code == 200
    data = shipment_res.json()
    assert data["current_status"] == "IN_TRANSIT"

