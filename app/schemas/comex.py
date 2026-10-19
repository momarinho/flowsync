import re
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

# Padrão internacional ISO 6346: 4 letras maiúsculas + 7 dígitos numéricos
CONTAINER_ISO_REGEX = re.compile(r"^[A-Z]{4}\d{7}$")

# Padrão UN/LOCODE: 2 letras de país + 3 caracteres de localidade (ex: BRSSZ)
UN_LOCODE_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}$")

# Incoterms reconhecidos internacionalmente pela ICC
IncotermType = Literal["FOB", "CIF", "EXW", "DDP", "FCA", "CFR"]
CurrencyType = Literal["USD", "BRL", "EUR"]
ShipmentStatusType = Literal["BOOKED", "IN_TRANSIT", "CUSTOMS_CLEARANCE", "DELIVERED"]


class ShipmentPayloadSchema(BaseModel):
    """
    Dados do embarque marítimo contidos no webhook.
    """
    tracking_number: str = Field(..., min_length=5, description="Número de rastreamento do parceiro")
    bill_of_lading: str = Field(..., min_length=5, description="Conhecimento de Embarque Marítimo (BL)")
    container_number: str = Field(..., description="Número do contêiner no padrão ISO 6346(ex: MSCU1234567)")
    origin_port: str = Field(..., description="Porto de origem no padrão UN/LOCODE (ex: BRSSZ)")
    destination_port: str = Field(..., description="Porto de destino no padrão UN / LOCODE(ex: CNSHA)")
    incoterm: IncotermType = Field(..., description="Incoterm acordado para o frete")
    declared_value: float = Field(..., gt=0, description="Valor comercial declarado da carga")
    currency: CurrencyType = Field(default="USD", description="Moeda da transação")
    status: ShipmentStatusType = Field(default="BOOKED", description="Status logístico atual")

    @field_validator("container_number")
    @classmethod
    def validar_container_iso(cls, v: str) -> str:
        valor_limpo = v.strip().upper()
        if not CONTAINER_ISO_REGEX.match(valor_limpo):
            raise ValueError(
                f"Contêiner '{v}' inválido. Deve seguir o padrão mundial ISO 6346: 4 letras + 7 dígitos (ex: MSCU1234567)."
            )
        return valor_limpo

    @field_validator("origin_port", "destination_port")
    @classmethod
    def validar_un_locode(cls, v: str) -> str:
        valor_limpo = v.strip().upper()
        if not UN_LOCODE_REGEX.match(valor_limpo):
            raise ValueError(
                f"Porto '{v}' fora do padrão internacional UN/LOCODE (ex: BRSSZ para Santos, CNSHA para Xangai)."
            )
        return valor_limpo


class ComexWebhookInput(BaseModel):
    """
    Contrato completo da mensagem recebida via Webhook de armadores e portos.
    """
    event_id: str = Field(..., min_length=1, description="ID único do evento gerado pelo emissor")
    provider: str = Field(..., min_length=1, description="Nome do parceiro/armador(ex: MAERSK, MSC, SANTOS_PORT)")
    shipment: ShipmentPayloadSchema
