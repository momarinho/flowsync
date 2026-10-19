from sqlalchemy import Column, String, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class CoreShipment(Base):
    """
    Camada 2: Core
    Dados consolidados de embarques marítimos com integridade referencial.
    """
    __tablename__ = "core_shipments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_number = Column(String(100), unique=True, nullable=False)
    bill_of_lading = Column(String(100), nullable=False)
    container_number = Column(String(15), nullable=False)  # Padrão ISO 6346 (ex: MSCU1234567)
    origin_port = Column(String(10), nullable=False)       # UN/LOCODE (ex: BRSSZ)
    destination_port = Column(String(10), nullable=False)  # UN/LOCODE (ex: CNSHA)
    incoterm = Column(String(5), nullable=False)           # FOB, CIF, EXW, DDP, etc.
    declared_value = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False)           # USD, BRL, EUR
    current_status = Column(String(50), nullable=False)    # BOOKED, IN_TRANSIT, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    events = relationship("CoreShipmentEvent", back_populates="shipment", cascade="all, delete-orphan")

class CoreShipmentEvent(Base):
    """
    Eventos de rastreamento de navio/porto com trava de idempotência por hash.
    """
    __tablename__ = "core_shipment_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("core_shipments.id", ondelete="CASCADE"), nullable=False)
    event_code = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(100), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    idempotency_hash = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    shipment = relationship("CoreShipment", back_populates="events")
