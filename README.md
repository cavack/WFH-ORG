# WaterfallHunter

**Crypto Signal Intelligence System with AI-Powered Analysis**

WaterfallHunter is a real-time cryptocurrency trading signal system that monitors 150+ trading pairs across multiple exchanges (Binance, BingX, MEXC), analyzes market microstructure, and generates calibrated trading signals with entry, stop-loss, and take-profit levels.

## Features

### Signal Intelligence
- **Multi-exchange monitoring**: Binance, BingX, MEXC WebSocket feeds
- **Cascade intelligence**: Multi-level evidence cascade (orderbook, derivatives, cross-exchange)
- **Cross-exchange confirmation**: Signals verified across multiple venues
- **Anti-chase scoring**: Prevents entering during price chasing
- **Entry readiness scoring**: 0-100 score based on technical, risk, timing, and market factors
- **Cascade PASS mandatory**: All signals require cascade confirmation

### AI Analysis
- **Ollama (primary)**: Local LLM (qwen2.5:1.5b) for instant analysis
- **Gemini (fallback)**: Google Gemini Flash Lite when Ollama unavailable
- **Heuristic (final fallback)**: Rule-based analysis when AI providers fail
- AI provides: LONG/SHORT/WAIT recommendation, confidence score, reasoning

### Fundamental Analysis
- **DexScreener** (20% weight): On-chain DEX data
- **CoinGecko** (25% weight): Market cap, volume, community stats
- **LunarCrush** (35% weight): Social sentiment (requires API key)
- **X/Twitter** (20% weight): Social mentions (requires API key)

### Backtester V2
- **$100 initial capital**
- **30% max exposure** ($30 across all positions)
- **3 simultaneous positions** max
- **Dynamic leverage 4x-14x** based on signal confidence:
  - Readiness 80+: 12x base
  - Readiness 75+: 10x base
  - Readiness 70+: 7x base
  - Readiness 60+: 5x base
  - Below 60: 4x base
  - +2x bonus for cascade PASS
  - +2x bonus for cross-exchange confirmation
  - Capped at 14x
- **Partial TP closes**: 50% at TP1, 25% at TP2, 25% at TP3
- **Self-learning mistake journal**: SQLite-based pattern tracking
- **Historical backtest**: Uses real signal data from database

### Telegram Bot
- `/signals` — View active signals
- `/health` — System health report
- `/top` — Top candidates
- `/help` — List commands
- 12-hour health reports
- Signal alerts with TP/SL/EP

### Dashboard
- Live signal cards with EP/SL/TP
- Market overview (BTC/ETH prices, market sentiment)
- Top 5 candidates
- Backtester results widget
- Decision terminal
- Research & diagnostics panel

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Nginx (HTTPS)                     │
│              waterfall.booksreadlive.online           │
├─────────────────────┬───────────────────────────────┤
│   Frontend (Next.js) │      Backend (FastAPI)        │
│      Port 3000       │       Port 8000               │
│                      │  ┌─────────────────────────┐  │
│  - Dashboard         │  │  Signal Engine           │  │
│  - Signal cards      │  │  - Entry Decision        │  │
│  - Backtest widget   │  │  - Cascade Intelligence  │  │
│  - Market overview   │  │  - AI Signal Advisor     │  │
│                      │  │  - Fundamental Scorer    │  │
│                      │  │  - Backtester V2         │  │
│                      │  │  - Telegram Enhanced     │  │
│                      │  └─────────────────────────┘  │
│                      │  ┌─────────────────────────┐  │
│                      │  │  WebSocket Feeds         │  │
│                      │  │  - Binance  - BingX     │  │
│                      │  │  - MEXC                 │  │
│                      │  └─────────────────────────┘  │
├─────────────────────┴───────────────────────────────┤
│              Docker Containers (application)         │
│  - waterfall-backend (2GB RAM)                       │
│  - waterfall-frontend                               │
│  - waterfall-watchdog                               │
│  - prometheus + grafana + alertmanager              │
├─────────────────────────────────────────────────────┤
│              Ollama (localhost:11434)                │
│              qwen2.5:1.5b (CPU mode)                 │
└─────────────────────────────────────────────────────┘
```

## Key Model Parameters (Calibrated)

| Parameter | Value | Description |
|-----------|-------|-------------|
| entry_ready_minimum | 70 | Minimum readiness score for ENTRY_READY |
| forming_minimum | 55 | Minimum readiness score for FORMING |
| coverage_threshold | 55 | Min exchange coverage % |
| max_leverage | 14 | Maximum leverage |
| max_exposure | 30% | Max capital exposure across positions |
| max_positions | 3 | Max simultaneous positions |
| initial_capital | $100 | Backtester starting capital |
| risk_per_trade | 10% | Max risk per position |
| cascade | MANDATORY | Cascade PASS required for all signals |
| AI provider | Ollama | Primary (qwen2.5:1.5b) |
| Gemini | Fallback | When Ollama fails |
| Heuristic | Final fallback | Rule-based |

## Backtest Results (Historical)

Using 3,381 real signals from the database:

| Config | Score Threshold | Win Rate | Return | Max DD | Trades |
|--------|----------------|----------|--------|--------|--------|
| Baseline | >=65 | 35.7% | 51.2% | 7.0% | 28 |
| **Optimal** | **>=70** | **66.7%** | **47.4%** | **2.1%** | **6** |
| Strict | >=75 | — | — | — | 0 |

**Optimal configuration**: Score >= 70, TP2 strategy, max 14x leverage

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/candidates` | All tracked candidates with metrics |
| `/api/health` | System health status |
| `/api/backtest/results` | Backtester V2 results |
| `/api/ai-advisory?symbol=X` | AI analysis for a symbol |
| `/api/fundamental?symbol=X` | Fundamental score for a symbol |
| `/dashboard/api/stream` | SSE stream for live updates |

## Deployment

### Build
```bash
cd /srv/waterfallhunter/app
docker build -t wfh-release-backend:calibrated -f backend/Dockerfile backend/
docker build -t wfh-release-frontend:calibrated -f frontend/Dockerfile frontend/
```

### Run Backend
```bash
docker run -d --name waterfall-backend --restart unless-stopped \
  --memory="2g" --memory-swap="2g" \
  --env-file /srv/waterfallhunter/.env \
  -v <data_volume>:/app/data \
  -e DATABASE_PATH=/app/data/waterfall_registry.db \
  --add-host=host.docker.internal:host-gateway \
  --network application --network egress --network edge \
  wfh-release-backend:calibrated
```

### Run Frontend
```bash
docker run -d --name waterfall-frontend --restart unless-stopped \
  -p 3000:3000 \
  --network application --network edge \
  wfh-release-frontend:calibrated
```

## Configuration (.env)

```env
TELEGRAM_TOKEN=<bot_token>
TELEGRAM_CHAT_ID=<chat_id>
GEMINI_API_KEY=<api_key>
GEMINI_MODEL=gemini-flash-lite-latest
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:1.5b
DEXSCREENER_ENABLED=true
COINGLASS_API_KEY=<api_key>
BACKTESTER_INITIAL_CAPITAL=100.0
BACKTESTER_MAX_LEVERAGE=14
BACKTESTER_MAX_EXPOSURE_PCT=30.0
BACKTESTER_MAX_POSITIONS=3
TELEGRAM_HEALTH_REPORT_INTERVAL=43200
```

## Tech Stack

- **Backend**: Python, FastAPI, WebSockets, SQLite
- **Frontend**: Next.js 16, TypeScript, TailwindCSS
- **AI**: Ollama (qwen2.5:1.5b), Google Gemini Flash Lite
- **Infrastructure**: Docker, Nginx, Prometheus, Grafana
- **Exchanges**: Binance, BingX, MEXC (WebSocket)
- **Data**: DexScreener, CoinGecko, LunarCrush, CoinGlass

## License

Private — WaterfallHunter Team
