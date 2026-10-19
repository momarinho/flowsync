import pytest
from pydantic import ValidationError
from app.schemas.comex import ComexWebhookInput, ShipmentPayloadSchema

def test_valid_comex_shipment():
    payload = {
        "event_id": "evt-maersk-98765",
        "provider": "MAERSK",
        "shipment": {
            "tracking_number": "TRK-2026-BR-001",
            "bill_of_lading": "MEDU99201928",
            "container_number": "MSCU1234567",
            "origin_port": "BRSSZ",       # Santos/BR
            "destination_port": "CNSHA",  # Shanghai/CN
            "incoterm": "FOB",
            "declared_value": 45000.50,
            "currency": "USD",
            "status": "IN_TRANSIT"
        }
    }
    data = ComexWebhookInput(**payload)
    assert data.provider == "MAERSK"
    assert data.shipment.container_number == "MSCU1234567"
    assert data.shipment.origin_port == "BRSSZ"
    assert data.shipment.declared_value == 45000.50

def test_invalid_container_format_raises_error():
    payload = {
        "tracking_number": "TRK-001",
        "bill_of_lading": "BL-001",
        "container_number": "CONTAINER_INVALIDO",  # Quebra o padrão ISO 6346
        "origin_port": "BRSSZ",
        "destination_port": "CNSHA",
        "incoterm": "FOB",
        "declared_value": 1000.0,
        "currency": "USD",
        "status": "BOOKED"
    }
    with pytest.raises(ValidationError) as exc_info:
        ShipmentPayloadSchema(**payload)
    assert "ISO 6346" in str(exc_info.value)

def test_invalid_port_code_raises_error():
    payload = {
        "tracking_number": "TRK-001",
        "bill_of_lading": "BL-001",
        "container_number": "MSCU1234567",
        "origin_port": "PORTO_DE_SANTOS",  # Quebra o padrão UN/LOCODE (espera 5 letras ex: BRSSZ)
        "destination_port": "CNSHA",
        "incoterm": "FOB",
        "declared_value": 1000.0,
        "currency": "USD",
        "status": "BOOKED"
    }
    with pytest.raises(ValidationError) as exc_info:
        ShipmentPayloadSchema(**payload)
    assert "UN/LOCODE" in str(exc_info.value)
