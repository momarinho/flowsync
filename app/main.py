from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.core.database import get_db
import app.models  # Registra os modelos

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    ## 🚢 FlowSync: Resilient Comex Data Ingestion & Integration Engine
    
    Motor de ingestão resiliente projetado para a **Flowls** (Logística Internacional & Comex).
    
    ### Arquitetura de 3 Camadas:
    1. **Staging:** Ingestão bruta auditável com validação de assinatura HMAC SHA-256.
    2. **Core:** Dados consolidados de embarques marítimos com integridade referencial ACID.
    3. **Quarentena:** Isolamento inteligente de dados com quebra de contrato sem falhar a API.
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Status"])
def root():
    return {
        "sistema": settings.PROJECT_NAME,
        "versao": settings.VERSION,
        "status": "OPERATIONAL",
        "docs": "/docs",
        "database": "PostgreSQL 16 (ACID + JSONB)"
    }

@app.get("/health", tags=["Status"])
def health_check(db: Session = Depends(get_db)):
    # Testa a conectividade com o PostgreSQL
    db.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "postgres": "connected",
        "layers": ["staging_events", "core_shipments", "quarantine_events"]
    }
