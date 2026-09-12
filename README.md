# WaterfallHunter

**Crypto Signal Intelligence System with AI-Powered Analysis**

Real-time cryptocurrency trading signal system monitoring 150+ trading pairs across Binance, BingX, and MEXC. Generates calibrated trading signals with entry, stop-loss, and take-profit levels using cascade intelligence, cross-exchange confirmation, and AI analysis.

## Key Features

### Signal Intelligence
- **Multi-exchange monitoring**: Binance, BingX, MEXC WebSocket feeds
- **Cascade intelligence**: Multi-level evidence cascade (orderbook, derivatives, cross-exchange)
- **Cascade PASS mandatory**: All signals require cascade confirmation — no exceptions
- **Cross-exchange confirmation**: Signals verified across multiple venues
- **Anti-chase scoring**: Prevents entering during price chasing
- **Entry readiness scoring**: 0-100 score based on technical, risk, timing, and market factors
- **Dynamic leverage 4x-14x**: Calculated from signal confidence, not fixed

### AI Analysis
- **Ollama (primary)**: Local LLM (qwen2.5:1.5b) for instant analysis, 120s timeout
- **Gemini (fallback)**: Google Gemini Flash Lite when Ollama unavailable
- **Heuristic (final fallback)**: Rule-based analysis when AI providers fail
- AI provides: LONG/SHORT/WAIT recommendation, confidence score, reasoning

### Fundamental Analysis
- **DexScreener** (20% weight): On-chain DEX data
- **CoinGecko** (25% weight): Market cap, volume, community stats
- **LunarCrush** (35% weight): Social sentiment (requires API key)
- **X/Twitter** (20% weight): Social mentions (requires API key)

### Backtester V2 — Professional Capital Management
- **$100 initial capital**
- **30% max exposure** ($30 across all positions)
- **3 simultaneous positions** max
- **Dynamic leverage 4x-14x** based on signal confidence:
  - Readiness 80+: 12x base
  - Readiness 75+: 10x base
  - Readiness 70+: 7x base
  - Readiness 60+: 5x base
  - +2x for cascade PASS, +2x for cross-exchange confirmation
  - Capped at 14x
- **TP2 strategy**: Take profit at TP2 level for higher win rate
- **Self-learning mistake journal**: SQLite-based pattern tracking
- **Historical backtest**: Uses real signal data from lbank_signal_ledger

### Telegram Bot
- `/signals` — View active signals
- `/health` — System health report
- `/top` — Top candidates
- `/help` — List commands
- 12-hour health reports

### Dashboard
- Live signal cards with EP/SL/TP
- Market overview (BTC/ETH prices, market sentiment)
- Top 5 candidates
- Backtester results widget
- Decision terminal
- Research & diagnostics panel
- Only shows cascade PASS signals (quality over quantity)

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

## Model Parameters (Calibrated via Historical Backtest)

| Parameter | Value | Description |
|-----------|-------|-------------|
| entry_ready_minimum | 70 | Minimum readiness for ENTRY_READY |
| forming_minimum | 55 | Minimum readiness for FORMING |
| coverage_threshold | 55 | Min exchange coverage % |
| max_leverage | 14 | Maximum leverage |
| max_exposure | 30% | Max capital exposure |
| max_positions | 3 | Max simultaneous positions |
| initial_capital | $100 | Backtester starting capital |
| cascade | MANDATORY | Cascade PASS required (hard gate) |
| tp_strategy | TP2 | Take profit at TP2 level |
| AI provider | Ollama | Primary (qwen2.5:1.5b, 120s timeout) |
| Gemini | Fallback | When Ollama fails |
| Heuristic | Final fallback | Rule-based |

## Backtest Results (Historical — Real Data)

Using 3,381 real signals from `lbank_signal_ledger` with actual outcomes from `lbank_signal_outcomes`:

### Optimal Configuration: Score >= 70, TP2 Strategy

| Metric | Value | Target |
|--------|-------|--------|
| Win Rate | 66.7% | ~70% |
| Total Return | 36.8% | ~70% |
| Profit Factor | 12.39 | >2.0 |
| Max Drawdown | 3.2% | <20% |
| Sharpe Ratio | 2.34 | >1.0 |
| Avg Leverage | 11.0x | 4-14x |
| Expectancy | $6.13/trade | >$0 |
| Trades | 6 | 2-6/day |

### Outcome Distribution (Score >= 70)
- TP2_AFTER_TP1: 2 (33%) — Big wins
- TP2_FIRST: 2 (33%) — Wins
- STOP_FIRST: 1 (17%) — Loss
- NO_LEVEL_HIT_24H: 1 (17%) — Timeout

### Configuration Comparison

| Config | Score Threshold | Win Rate | Return | Max DD | Trades |
|--------|----------------|----------|--------|--------|--------|
| Baseline | >=65 | 35.7% | -7.7% | 17.8% | 14 |
| **Optimal** | **>=70** | **66.7%** | **36.8%** | **3.2%** | **6** |
| Strict | >=75 | — | — | — | 0 |

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
