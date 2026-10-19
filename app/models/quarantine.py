from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class QuarantineEvent(Base):
    """
    Camada 3: Quarentena
    Isolamento de payloads com quebra de contrato ou dados sujos.
    Permite à esteira continuar funcionando sem perder o dado com falha.
    """
    __tablename__ = "quarantine_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staging_event_id = Column(UUID(as_uuid=True), ForeignKey("staging_events.id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(50), nullable=False)
    raw_payload = Column(JSONB, nullable=False)
    rejection_reason = Column(String(100), nullable=False)  # CONTRACT_VALIDATION_FAILED, etc.
    validation_errors = Column(JSONB, nullable=False)       # Relatório de erros do Pydantic
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
