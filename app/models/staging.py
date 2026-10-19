from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class StagingEvent(Base):
    """
    Camada 1: Staging
    Ingestão bruta em alta velocidade para auditoria e replay de webhooks.
    """
    __tablename__ = "staging_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)  # MAERSK, MSC, HAPAG_LLOYD, etc.
    raw_payload = Column(JSONB, nullable=False)
    signature = Column(String(255), nullable=True)
    status = Column(String(30), default="PENDING")  # PENDING, PROCESSED, QUARANTINED
    received_at = Column(DateTime(timezone=True), server_default=func.now())
