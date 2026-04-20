import math
import requests
from datetime import datetime

PIPELINE_ID  = "63fe4bd368b6a60016d11684"
STAGE_SQL_ID = "63fe4bd368b6a60016d11689"
_BASE_URL    = "https://crm.rdstation.com/api/v1"


def classificar_regional(deal: dict) -> str:
    esquadrao, estado_origem = None, None
    for cf in deal.get("deal_custom_fields", []):
        label = (cf.get("custom_field") or {}).get("label", "").lower()
        value = cf.get("value")
        if not value:
            continue
        val = str(value[0] if isinstance(value, list) else value).strip()
        if "esquadr" in label:
            esquadrao = val.upper()
        elif "estado" in label and "origem" in label:
            estado_origem = val.upper()
    if esquadrao == "ALFA":    return "PE"
    if esquadrao == "BRAVO":   return "BA"
    if esquadrao == "CHARLIE": return "SP"
    if estado_origem:
        if "PERNAMBUCO" in estado_origem or estado_origem == "PE": return "PE"
        if "BAHIA"      in estado_origem or estado_origem == "BA": return "BA"
        if "SÃO PAULO"  in estado_origem or "SAO PAULO" in estado_origem or estado_origem == "SP":
            return "SP"
    return "OUTROS"


def _norm_source(name: str) -> str:
    sl = str(name or "").strip().lower()
    return "Organic" if sl in (
        "organic", "organico", "orgânico", "indicação", "indicacao", "referral"
    ) else "Digital"


def buscar_sqls_crm(token: str) -> tuple[list, str | None]:
    deals, next_pg, total = [], None, None
    while True:
        params = {"token": token, "deal_stage_id": STAGE_SQL_ID, "limit": 200}
        if next_pg:
            params["page"] = next_pg
        try:
            r = requests.get(f"{_BASE_URL}/deals", params=params, timeout=15)
            r.raise_for_status()
        except requests.RequestException as exc:
            return deals, str(exc)
        data  = r.json()
        batch = data.get("deals", [])
        deals.extend(batch)
        if total is None:
            total = data.get("total", 0)
        if len(deals) >= total:   break
        if not data.get("has_more"): break
        next_pg = data.get("next_page")
        if not next_pg: break
    seen, unique = set(), []
    for d in deals:
        if d["_id"] not in seen:
            seen.add(d["_id"])
            unique.append(d)
    return unique, None


def deals_para_rows(deals: list) -> list:
    """Converte lista de deals da RD Station para linhas prontas para o SQLite."""
    now  = datetime.utcnow().isoformat()
    rows = []
    for deal in deals:
        try:
            dt = datetime.fromisoformat(deal["created_at"]).replace(tzinfo=None)
        except (KeyError, ValueError, TypeError):
            continue
        rows.append({
            "id":          deal["_id"],
            "created_at":  dt.isoformat(),
            "week":        math.ceil(dt.day / 7),
            "month":       dt.strftime("%B"),
            "year":        dt.year,
            "state":       classificar_regional(deal),
            "lead_source": _norm_source((deal.get("deal_source") or {}).get("name", "")),
            "sql_count":   1.0,
            "synced_at":   now,
        })
    return rows
