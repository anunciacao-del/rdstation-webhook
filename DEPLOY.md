# Deploy do Serviço de Webhook — Railway

## O que é
FastAPI que recebe eventos da RD Station CRM e persiste num banco SQLite.
O Dashboard Streamlit lê deste serviço em vez de chamar a API diretamente.

## Pré-requisitos
- Conta no [Railway](https://railway.app) (free tier suficiente)
- Token da API RD Station (`RDSTATION_TOKEN`)

---

## Passo 1 — Criar repositório GitHub

Crie um repositório novo (ex: `rdstation-webhook`) e suba apenas os arquivos desta pasta:

```
main.py
database.py
crm.py
requirements.txt
Procfile
```

---

## Passo 2 — Deploy no Railway

1. Acesse railway.app → **New Project → Deploy from GitHub repo**
2. Selecione o repositório criado
3. Railway detecta o `Procfile` automaticamente

---

## Passo 3 — Variáveis de ambiente no Railway

Em **Settings → Variables**, adicione:

| Variável | Valor |
|----------|-------|
| `RDSTATION_TOKEN` | Token da API RD Station |
| `PORT` | `8000` (Railway preenche automaticamente) |

---

## Passo 4 — Copiar a URL pública do serviço

Após o deploy, Railway fornece uma URL como:
```
https://rdstation-webhook-production.up.railway.app
```

---

## Passo 5 — Configurar no Streamlit Cloud

Em **App settings → Secrets**, adicione:

```toml
WEBHOOK_SERVICE_URL = "https://rdstation-webhook-production.up.railway.app"
```

O dashboard vai priorizar o serviço e só usar a API direta como fallback.

---

## Passo 6 — Configurar webhook na RD Station

1. No painel RD Station CRM → **Configurações → Webhooks**
2. Clique em **Novo webhook**
3. Configure:
   - **URL:** `https://sua-url.up.railway.app/webhook/rdstation`
   - **Evento:** Deal — Etapa alterada
   - **Funil:** RPS
   - **Etapa:** Agendamento reunião de fechamento
4. Salve

---

## Endpoints disponíveis

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/webhook/rdstation` | Recebe evento da RD Station |
| `GET`  | `/deals` | Retorna todos os SQLs (usado pelo dashboard) |
| `GET`  | `/status` | Total de deals e última sincronização |
| `POST` | `/sync`   | Força polling manual |
| `GET`  | `/health` | Health check |

---

## Teste rápido após deploy

```bash
curl https://sua-url.up.railway.app/health
# {"status":"ok","timestamp":"..."}

curl https://sua-url.up.railway.app/status
# {"total_deals":0,"last_sync":null,"timestamp":"..."}
```

O polling automático é executado 1 minuto após o startup e depois a cada hora,
carregando todos os deals históricos da etapa SQL.
