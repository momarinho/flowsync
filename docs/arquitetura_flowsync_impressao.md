# 🚢 Proposta Arquitetural de Integração — Ecossistema Flowls (`FlowSync PoC`)
**Candidato:** Mateus Marinho | **Foco:** Engenharia de Integrações, APIs REST (Python/FastAPI), PostgreSQL 16 & Resiliência Comex  
**Repositório / Portfólio:** `github.com/momarinho/flowsync` | `portfoliomomarinho.vercel.app`

---

## 1. Diagrama do Fluxo de Arquitetura (Armadores & ERPs → Ingestão Webhook → 3 Camadas)

```text
+---------------------------------------------------------------------------------------------------+
|                                   FONTES DE ENTRADA / CLIENTES                                    |
+-------------------------------------------------+-------------------------------------------------+
|          ARMADORES & PORTOS (Maersk, MSC, etc.) |          ERPs ENTERPRISE (SAP, Totvs, Omie)     |
|  • Webhooks de rastreamento de contêineres      |  • Despacho aduaneiro (DUIMP, Commercial Inv.)  |
|  • Atualização de status e janelas de atracação |  • Planilhas de despachantes com dados caóticos |
+------------------------+------------------------+------------------------+------------------------+
                         |                                                 |
                         | HTTPS POST + Header: X-Flowls-Signature (HMAC)  | Ingestão em Lote / Webhook
                         v                                                 v
+---------------------------------------------------------------------------------------------------+
|                        GATEWAY DE INGESTÃO RESILIENTE (FastAPI / FlowSync)                        |
|                                                                                                   |
|  1. VALIDAÇÃO DE ASSINATURA HMAC SHA-256        2. RESPOSTA IMEDIATA EM < 50ms                    |
|     Rejeita fraudes na borda antes de gastar       Grava o payload bruto em Staging e devolve     |
|     CPU com parsing ou operações pesadas.          HTTP 202 Accepted. Nunca causa timeout.        |
|                                                                                                   |
|  3. VALIDAÇÃO DE CONTRATOS COMEX (Pydantic v2)  4. ENCAMINHAMENTO RESILIENTE (Core vs Quarentena) |
|     Padrão ISO 6346 (4 letras + 7 dígitos) e       Válido -> Core com transação ACID.             |
|     portos mundiais UN/LOCODE (ex: BRSSZ).         Inválido -> Quarentena com log detalhado.      |
+------------------------+-------------------------------------------------+------------------------+
                         |                                                 |
                         | DADOS ÍNTEGROS (ACID + Idempotência)            | DADOS COM QUEBRA DE CONTRATO
                         v                                                 v
+-------------------------------------------------+-------------------------------------------------+
|        CAMADA 2: CORE CANÔNICO COMEX            |          CAMADA 3: QUARENTENA & ANOMALIAS       |
|  • Tabelas: core_shipments e shipment_events    |  • Tabela: quarantine_events (JSONB estruturado)|
|  • Chave de Idempotência: Hash SHA-256          |  • Preserva o dado bruto e detalha campo falho  |
|  • Impede duplicidade de eventos de navio/porto |  • Dispara Webhook no n8n -> Alerta Slack       |
+-------------------------------------------------+-------------------------------------------------+
```

---

## 2. Rotas OpenAPI/Swagger & Modelagem Relacional de Controle

### Endpoints Expostos no Gateway FastAPI (`/docs`):
* `POST /api/v1/webhooks/comex` — Ingestão assíncrona de webhooks com HMAC e retorno em menos de 50ms.
* `POST /api/v1/webhooks/comex/sync` — Ingestão síncrona para auditoria imediata e testes automatizados.
* `GET  /api/v1/shipments/{tracking}` — Consulta dados consolidados do embarque e histórico de rastreamento.
* `GET  /api/v1/quarantine` — Listagem de anomalias operacionais para a equipe de suporte e integrações.
* `POST /api/v1/quarantine/{id}/resolve` — Marcação de anomalia como resolvida após correção manual.
* `GET  /api/v1/metrics` — Métricas em tempo real extraídas da View SQL (`total_ingested`, taxa de sucesso).

### Estrutura das Tabelas de Governança e Rastreabilidade (`PostgreSQL 16`):
| Tabela `staging_events` (Auditoria Bruta) | Tabela `core_shipments` (Consolidada) | Tabela `quarantine_events` (Isolamento) |
| :--- | :--- | :--- |
| • `id` *(UUID PK)* / `event_id` | • `tracking_number` *(UNIQUE INDEX)* | • `staging_event_id` *(FK Staging)* |
| • `provider` (`MAERSK`, `MSC`, etc.) | • `container_number` *(ISO 6346)* | • `rejection_reason` (`CONTRACT_FAILED`) |
| • `raw_payload` *(JSONB auditável)* | • `origin_port` & `destination_port` *(UN/LOCODE)* | • `validation_errors` *(Log Pydantic/Zod)* |
| • `status` (`PENDING`, `PROCESSED`, `QUARANTINED`)| • `incoterm` (`FOB`, `CIF`, `EXW`, `DDP`) | • `resolved` *(BOOLEAN de controle)* |
| • `signature` *(Hash HMAC recebido)* | • `declared_value` *(NUMERIC)* / `currency` | • `created_at` *(Timestamp)* |

---

## 3. Prova de Execução dos Testes Automatizados (`pytest tests/ -v`)

```text
============================== test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.7.0
rootdir: /home/mateus/Projects/flowsync

tests/test_pipeline.py::test_health_check PASSED                                [ 10%]
tests/test_pipeline.py::test_webhook_invalid_hmac_rejected PASSED               [ 20%]
tests/test_pipeline.py::test_webhook_valid_payload_processed_to_core PASSED     [ 30%]
tests/test_pipeline.py::test_webhook_corrupted_payload_goes_to_quarantine PASSED [ 40%]
tests/test_pipeline.py::test_integration_metrics_endpoint PASSED                [ 50%]
tests/test_pipeline.py::test_resolve_quarantine_item PASSED                      [ 60%]
tests/test_pipeline.py::test_idempotent_duplicate_webhook PASSED                 [ 70%]
tests/test_schemas.py::test_valid_comex_shipment PASSED                          [ 80%]
tests/test_schemas.py::test_invalid_container_format_raises_error PASSED         [ 90%]
tests/test_schemas.py::test_invalid_port_code_raises_error PASSED                [100%]

======================== 10 passed, 1 warning in 0.38s =========================
```

---

## 4. Diferenciais de Engenharia Demonstrados para a Flowls

1. **Tolerância a Falhas Real:** A API nunca derruba a conexão (`500`) por dado corrompido do parceiro. O erro é isolado na Quarentena com o log cirúrgico do campo defeituoso.
2. **Governança de Padrões Internacionais:** Validação nativa de contêineres **ISO 6346** e portos **UN/LOCODE** direto no contrato da API.
3. **Ponte Low-Code com n8n:** Workflow exportado (`n8n/quarantine_alert_workflow.json`) que consome anomalias e alerta o time de operações no Slack/Discord.
