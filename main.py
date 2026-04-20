import logging
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from crm import STAGE_SQL_ID, buscar_sqls_crm, deals_para_rows
from database import (
    get_all_deals,
    get_db,
    get_last_sync,
    init_db,
    log_sync,
    upsert_deal,
    get_existing_ids,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RDSTATION_TOKEN = os.environ.get("RDSTATION_TOKEN", "")

app = FastAPI(title="RD Station Webhook Service", version="1.0.0")


# ─── STARTUP ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(sync_polling, "interval", hours=1, id="hourly_polling",
                      next_run_time=datetime.now())
    scheduler.start()
    logger.info("Scheduler iniciado — polling a cada 1 hora")


# ─── WEBHOOK ──────────────────────────────────────────────────────────────────

@app.post("/webhook/rdstation")
async def webhook_rdstation(request: Request):
    """
    Recebe evento da RD Station quando um deal muda de etapa.
    Aceita tanto o deal direto quanto encapsulado em {"deal": {...}}.
    Retorna 200 imediatamente para não causar timeout no CRM.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "detail": "invalid json"}, status_code=400)

    # RD Station pode enviar o deal encapsulado ou diretamente
    deal = payload.get("deal") if isinstance(payload, dict) and "deal" in payload else payload

    if not isinstance(deal, dict) or not deal.get("_id"):
        return {"status": "ignored", "reason": "no deal id"}

    # Filtra apenas a etapa SQL
    stage_id = (deal.get("deal_stage") or {}).get("_id", "")
    if stage_id and stage_id != STAGE_SQL_ID:
        return {"status": "ignored", "reason": "not sql stage"}

    rows = deals_para_rows([deal])
    if rows:
        with get_db() as conn:
            for row in rows:
                upsert_deal(conn, row)
            log_sync(conn, len(rows), "webhook")
        logger.info(f"Webhook: {len(rows)} deal(s) persistido(s) [{deal['_id']}]")

    return {"status": "ok", "deals_saved": len(rows)}


# ─── LEITURA ──────────────────────────────────────────────────────────────────

@app.get("/deals")
def get_deals():
    """Retorna todos os SQLs do banco para o dashboard Streamlit."""
    with get_db() as conn:
        return get_all_deals(conn)


@app.get("/status")
def status():
    """Retorna contagem de deals e última sincronização."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM sqls").fetchone()[0]
        last  = get_last_sync(conn)
    return {
        "total_deals": total,
        "last_sync":   last,
        "timestamp":   datetime.utcnow().isoformat(),
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ─── SYNC MANUAL ──────────────────────────────────────────────────────────────

@app.post("/sync")
def force_sync(background_tasks: BackgroundTasks):
    """Aciona o polling manualmente (ex: botão 'Forçar atualização' no dashboard)."""
    background_tasks.add_task(sync_polling)
    return {"status": "sync started"}


# ─── POLLING HORÁRIO ──────────────────────────────────────────────────────────

def sync_polling():
    if not RDSTATION_TOKEN:
        logger.warning("RDSTATION_TOKEN não configurado — polling ignorado")
        return

    logger.info("Polling CRM iniciado...")
    deals, err = buscar_sqls_crm(RDSTATION_TOKEN)
    if err:
        logger.error(f"Erro no polling: {err}")
        return

    rows = deals_para_rows(deals)
    new_count = 0
    with get_db() as conn:
        existing = get_existing_ids(conn)
        for row in rows:
            upsert_deal(conn, row)
            if row["id"] not in existing:
                new_count += 1
        log_sync(conn, new_count, "polling")

    logger.info(f"Polling concluído: {len(rows)} deals totais, {new_count} novos")
