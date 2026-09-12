"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, Wifi, WifiOff, Clock3, TrendingDown, TrendingUp, Zap, Target, Shield, BarChart3, ChevronDown, Radio, FlaskConical } from "lucide-react";
import { Candidate, ScoreCard } from "@/components/score-card";
import { MarketContext } from "@/components/market-context";
import { DecisionTerminal, CandidateTable } from "@/components/decision-terminal";
import { OutcomeEvidence } from "@/components/outcome-evidence";
import { RecentSignals } from "@/components/recent-signals";
import { HistoricalOutcomes } from "@/components/historical-outcomes";
import { ProductionEvidence } from "@/components/production-evidence";
import { FeatureReplay } from "@/components/feature-replay";
import { LifecycleShadow } from "@/components/lifecycle-shadow";
import { BacktestLab } from "@/components/backtest-lab";
import { SignalFunnel, SignalFunnelData } from "@/components/signal-funnel";
import { FinalRanking } from "@/components/final-ranking";
import type { DashboardSnapshot } from "@/generated/dashboard-contract";
import { dashboardSnapshot, dashboardStreamEvent } from "@/lib/dashboard-contract";
import { summarizeCandidateFreshness } from "@/lib/decision-terminal-ui";

type ConnectionMode = "stream" | "polling" | "reconnecting";

function connectionLabel(mode: ConnectionMode): string {
  if (mode === "stream") return "Live";
  if (mode === "polling") return "Polling";
  return "Reconnecting…";
}

function boundedJitter(maximum: number): number {
  const sample = new Uint32Array(1);
  globalThis.crypto.getRandomValues(sample);
  return Math.floor((sample[0] / 0xffffffff) * maximum);
}

/* ─── Type helpers ─── */
function getMetrics(candidate: Candidate): Record<string, unknown> | undefined {
  const m = candidate.metrics;
  return m !== null && typeof m === "object" && !Array.isArray(m) ? m as Record<string, unknown> : undefined;
}

function getED(candidate: Candidate): Record<string, unknown> | undefined {
  const m = getMetrics(candidate);
  const ed = m?.entry_decision;
  return ed !== null && typeof ed === "object" && !Array.isArray(ed) ? ed as Record<string, unknown> : undefined;
}

function getReadiness(candidate: Candidate): number {
  const r = getED(candidate)?.entry_readiness;
  return typeof r === "number" && Number.isFinite(r) ? r : 0;
}

function getDecision(candidate: Candidate): string {
  return (getED(candidate)?.decision as string) ?? "—";
}

function getTradePlan(candidate: Candidate): Record<string, unknown> | null {
  const tp = getED(candidate)?.trade_plan;
  return tp !== null && typeof tp === "object" && !Array.isArray(tp) ? tp as Record<string, unknown> : null;
}

function getReasons(candidate: Candidate): string[] {
  const r = getED(candidate)?.reason_codes;
  return Array.isArray(r) ? r.filter((x): x is string => typeof x === "string") : [];
}

/* ─── Signal Card ─── */
function SignalCard({ symbol, candidate, nowSeconds }: Readonly<{ symbol: string; candidate: Candidate; nowSeconds?: number }>) {
  const ed = getED(candidate);
  if (!ed) return null;
  const tradePlan = getTradePlan(candidate);
  if (!tradePlan) return null;
  const ep = tradePlan.entry_price as number | undefined;
  const sl = tradePlan.stop_loss as number | undefined;
  const tp1 = tradePlan.take_profit_1 as number | undefined;
  const tp2 = tradePlan.take_profit_2 as number | undefined;
  const tp3 = tradePlan.take_profit_3 as number | undefined;
  const r2r = tradePlan.reward_to_risk as number | undefined;
  const leverage = tradePlan.leverage as number | undefined;
  const readiness = (ed.entry_readiness as number) ?? 0;
  const es = getED(candidate)?.evidence_summary as Record<string, unknown> | undefined;
  const cascade = es?.cascade as Record<string, unknown> | undefined;
  const cross = es?.cross_exchange_confirmed as boolean | undefined;
  const reasons = getReasons(candidate);
  const lastPrice = candidate.last_price as number | undefined;

  const fmt = (v: number | undefined) => v !== undefined ? v.toFixed(v < 1 ? 6 : 4) : "—";
  const pnl = ep && sl ? Math.abs((ep - sl) / ep * 100).toFixed(2) : "—";

  return (
    <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Zap size={18} className="text-emerald-400" />
          <span className="text-lg font-bold text-emerald-300">{symbol.replace("/USDT:USDT", "")}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-300">ENTRY READY</span>
          <span className="font-mono text-sm text-slate-400">R: {readiness.toFixed(1)}</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div className="rounded-lg bg-slate-900/50 p-2">
          <div className="text-xs text-slate-500">Entry Price</div>
          <div className="font-mono font-semibold text-sky-300">{fmt(ep)}</div>
        </div>
        <div className="rounded-lg bg-slate-900/50 p-2">
          <div className="text-xs text-slate-500">Stop Loss</div>
          <div className="font-mono font-semibold text-rose-300">{fmt(sl)}</div>
        </div>
        <div className="rounded-lg bg-slate-900/50 p-2">
          <div className="text-xs text-slate-500">Take Profit 1</div>
          <div className="font-mono font-semibold text-emerald-300">{fmt(tp1)}</div>
        </div>
        <div className="rounded-lg bg-slate-900/50 p-2">
          <div className="text-xs text-slate-500">Take Profit 2</div>
          <div className="font-mono font-semibold text-emerald-400">{fmt(tp2)}</div>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
        {tp3 !== undefined && tp3 !== null && <span className="rounded bg-slate-800/50 px-1.5 py-0.5">TP3: {fmt(tp3)}</span>}
        {r2r !== undefined && <span className="rounded bg-slate-800/50 px-1.5 py-0.5">R:R = 1:{r2r}</span>}
        {leverage !== undefined && leverage !== null && <span className="rounded bg-slate-800/50 px-1.5 py-0.5">Lev: {leverage}x</span>}
        {pnl !== "—" && <span className="rounded bg-slate-800/50 px-1.5 py-0.5">Risk: {pnl}%</span>}
        {lastPrice !== undefined && <span className="rounded bg-slate-800/50 px-1.5 py-0.5">Last: {fmt(lastPrice)}</span>}
        {cascade && <span className="rounded bg-slate-800/50 px-1.5 py-0.5">Cascade: {String(cascade.status ?? "?")}</span>}
        {cross !== undefined && <span className="rounded bg-slate-800/50 px-1.5 py-0.5">Cross: {cross ? "✓" : "—"}</span>}
      </div>
      {reasons.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {reasons.filter(r => !r.startsWith("BELOW") && !r.startsWith("ABOVE")).map(r => (
            <span key={r} className="rounded bg-slate-800/40 px-1.5 py-0.5 text-[10px] text-slate-500">{r}</span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Market Overview ─── */
function MarketOverview({ candidates }: Readonly<{ candidates: Record<string, Candidate> }>) {
  const btc = candidates["BTC/USDT:USDT"];
  const eth = candidates["ETH/USDT:USDT"];

  const btcPrice = typeof btc?.last_price === "number" ? btc.last_price : undefined;
  const ethPrice = typeof eth?.last_price === "number" ? eth.last_price : undefined;

  // Determine market trend from candidate statuses
  const allCandidates = Object.values(candidates);
  const fuelRich = allCandidates.filter(c => c.status === "FUEL-RICH").length;
  const watch = allCandidates.filter(c => c.status === "WATCH").length;
  const preTrigger = allCandidates.filter(c => c.status === "PRE-TRIGGER").length;
  const triggered = allCandidates.filter(c => c.status === "TRIGGERED").length;
  const total = allCandidates.length;

  // Simple trend: if more fuel-rich than watch, market is bearish (hype cooling)
  const bearish = fuelRich > watch;
  const trendLabel = bearish ? "Bearish" : "Neutral";
  const TrendIcon = bearish ? TrendingDown : TrendingUp;
  const trendColor = bearish ? "text-rose-400" : "text-amber-400";

  // Count decisions
  const entryReady = allCandidates.filter(c => getDecision(c) === "ENTRY_READY" || getDecision(c) === "ACTIVE").length;
  const forming = allCandidates.filter(c => getDecision(c) === "FORMING").length;
  const late = allCandidates.filter(c => getDecision(c) === "LATE").length;

  const fmtPrice = (v: number | undefined) => {
    if (v === undefined) return "—";
    if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    if (v >= 1) return `$${v.toFixed(2)}`;
    return `$${v.toFixed(4)}`;
  };

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-3">
        <div className="flex items-center gap-1.5 text-xs text-amber-400/80"><span className="text-base">₿</span> BTC</div>
        <div className="mt-1 font-mono font-bold text-amber-200">{fmtPrice(btcPrice)}</div>
      </div>
      <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/10 p-3">
        <div className="flex items-center gap-1.5 text-xs text-indigo-400/80"><span className="text-base">Ξ</span> ETH</div>
        <div className="mt-1 font-mono font-bold text-indigo-200">{fmtPrice(ethPrice)}</div>
      </div>
      <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-3">
        <div className="flex items-center gap-1.5 text-xs text-slate-400"><TrendIcon size={14} className={trendColor} /> Trend</div>
        <div className={`mt-1 font-bold ${trendColor}`}>{trendLabel}</div>
      </div>
      <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-3">
        <div className="flex items-center gap-1.5 text-xs text-slate-400"><Radio size={14} /> Tracked</div>
        <div className="mt-1 font-mono font-bold text-slate-200">{total}</div>
      </div>
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-3">
        <div className="flex items-center gap-1.5 text-xs text-emerald-400/80"><Zap size={14} /> Signals</div>
        <div className="mt-1 font-mono font-bold text-emerald-300">{entryReady}</div>
      </div>
      <div className="rounded-xl border border-sky-500/20 bg-sky-950/10 p-3">
        <div className="flex items-center gap-1.5 text-xs text-sky-400/80"><Target size={14} /> Forming</div>
        <div className="mt-1 font-mono font-bold text-sky-300">{forming}</div>
      </div>
    </div>
  );
}

/* ─── Top Candidates Section ─── */
function TopCandidates({ rows, excludeSymbols }: Readonly<{ rows: [string, Candidate][]; excludeSymbols: Set<string> }>) {
  const top5 = rows
    .filter(([sym]) => !excludeSymbols.has(sym))
    .filter(([, c]) => {
      const r = getReadiness(c);
      return r > 0;
    })
    .sort(([, a], [, b]) => {
      const ra = getReadiness(a);
      const rb = getReadiness(b);
      return rb - ra;
    })
    .slice(0, 5);

  if (top5.length === 0) return null;

  return (
    <section>
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-300">
        <BarChart3 size={16} className="text-sky-400" /> Top Candidates
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {top5.map(([symbol, candidate]) => {
          const r = getReadiness(candidate);
          const dec = getDecision(candidate);
          const tp = getTradePlan(candidate);
          const es = getED(candidate)?.evidence_summary as Record<string, unknown> | undefined;
          const cascade = es?.cascade as Record<string, unknown> | undefined;
          const cross = es?.cross_exchange_confirmed as boolean | undefined;
          const reasons = getReasons(candidate);
          const decColor = dec === "ENTRY_READY" || dec === "ACTIVE"
            ? "text-emerald-400" : dec === "FORMING" ? "text-sky-400"
            : dec === "LATE" ? "text-amber-400" : "text-slate-400";

          return (
            <div key={symbol} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-200">{symbol.replace("/USDT:USDT", "")}</span>
                <span className={`text-xs font-semibold ${decColor}`}>{dec}</span>
              </div>
              <div className="mt-2 flex items-center justify-between text-sm">
                <span className="font-mono text-emerald-300">R: {r.toFixed(1)}</span>
                <span className="text-xs text-slate-500">{String(candidate.status ?? "—")}</span>
              </div>
              {tp && (
                <div className="mt-2 grid grid-cols-3 gap-1 text-xs">
                  <div className="text-slate-500">EP: <span className="font-mono text-sky-300">{((tp.entry_price as number) ?? 0).toFixed(4)}</span></div>
                  <div className="text-slate-500">SL: <span className="font-mono text-rose-300">{((tp.stop_loss as number) ?? 0).toFixed(4)}</span></div>
                  <div className="text-slate-500">TP: <span className="font-mono text-emerald-300">{((tp.take_profit_1 as number) ?? 0).toFixed(4)}</span></div>
                </div>
              )}
              <div className="mt-2 flex flex-wrap gap-1">
                {cross !== undefined && <span className={`rounded px-1 py-0.5 text-[10px] ${cross ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800/50 text-slate-500"}`}>Cross {cross ? "✓" : "—"}</span>}
                {cascade && <span className="rounded bg-slate-800/50 px-1 py-0.5 text-[10px] text-slate-500">{String(cascade.status ?? "?")}</span>}
                {reasons.includes("SELL_PRESSURE_CONFIRMED") && <span className="rounded bg-emerald-500/10 px-1 py-0.5 text-[10px] text-emerald-400">Sell ✓</span>}
                {reasons.includes("EXECUTION_OK") && <span className="rounded bg-sky-500/10 px-1 py-0.5 text-[10px] text-sky-400">Exec ✓</span>}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ─── Main Dashboard ─── */
export default function Dashboard() {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [mode, setMode] = useState<ConnectionMode>("reconnecting");
  const [generatedAt, setGeneratedAt] = useState<number | null>(null);
  const [freshnessNow, setFreshnessNow] = useState<number | undefined>(undefined);
  const [researchOpen, setResearchOpen] = useState(false);
  const latestVersion = useRef(0);
  const lastStreamEventAt = useRef(0);

  useEffect(() => {
    const refreshClock = () => setFreshnessNow(Date.now() / 1000);
    refreshClock();
    const timer = setInterval(refreshClock, 5_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let pollAttempt = 0;
    let streaming = false;
    let hasSnapshot = false;
    let streamWatchdog: ReturnType<typeof setInterval> | undefined;
    const stream = new EventSource("/dashboard/api/stream");

    const acceptSnapshot = (snapshot: DashboardSnapshot) => {
      if (!active || snapshot.snapshot_version <= latestVersion.current) return;
      latestVersion.current = snapshot.snapshot_version;
      hasSnapshot = true;
      setData(snapshot);
      setGeneratedAt(snapshot.generated_at * 1000);
    };

    const schedulePoll = (delay: number) => {
      if (!active || pollTimer !== undefined) return;
      const jitter = delay > 0 ? boundedJitter(Math.min(1_500, delay)) : 0;
      pollTimer = setTimeout(() => {
        pollTimer = undefined;
        if (!active) return;
        void (async () => {
          try {
            const response = await fetch("/dashboard/api/candidates", { cache: "no-store" });
            const snapshot = response.ok ? dashboardSnapshot(await response.json()) : undefined;
            if (!snapshot) throw new Error("invalid dashboard snapshot");
            acceptSnapshot(snapshot);
            pollAttempt = 0;
            if (streaming) return;
            setMode("polling");
            schedulePoll(5_000);
          } catch {
            pollAttempt += 1;
            if (!streaming) setMode("reconnecting");
            if (!streaming || !hasSnapshot) {
              schedulePoll(Math.min(30_000, 1_000 * (2 ** Math.min(pollAttempt, 5))));
            }
          }
        })();
      }, delay + jitter);
    };

    const handleStreamMessage = (event: MessageEvent<string>) => {
      try {
        const packet = dashboardStreamEvent(JSON.parse(event.data));
        if (!packet) throw new Error("invalid dashboard stream event");
        if (packet.payload) {
          acceptSnapshot(packet.payload);
          if (hasSnapshot && pollTimer !== undefined) {
            clearTimeout(pollTimer);
            pollTimer = undefined;
          }
        }
        lastStreamEventAt.current = Date.now();
        streaming = true;
        setMode("stream");
      } catch {
        streaming = false;
        setMode("reconnecting");
        schedulePoll(1_000);
      }
    };

    const handleNamedStreamEvent = (event: Event) => {
      if (event instanceof MessageEvent) {
        handleStreamMessage(event as MessageEvent<string>);
      }
    };

    stream.onopen = () => {
      pollAttempt = 0;
      if (!hasSnapshot) setMode("reconnecting");
    };
    stream.onerror = () => {
      streaming = false;
      setMode("reconnecting");
      schedulePoll(1_000);
    };
    stream.onmessage = handleStreamMessage;
    stream.addEventListener("snapshot", handleNamedStreamEvent);
    stream.addEventListener("heartbeat", handleNamedStreamEvent);
    schedulePoll(0);
    streamWatchdog = setInterval(() => {
      if (!active || !streaming || lastStreamEventAt.current <= 0) return;
      if (Date.now() - lastStreamEventAt.current > 45_000) {
        streaming = false;
        setMode("reconnecting");
        schedulePoll(0);
      }
    }, 5_000);

    return () => {
      active = false;
      stream.removeEventListener("snapshot", handleNamedStreamEvent);
      stream.removeEventListener("heartbeat", handleNamedStreamEvent);
      stream.close();
      if (pollTimer !== undefined) clearTimeout(pollTimer);
      if (streamWatchdog !== undefined) clearInterval(streamWatchdog);
    };
  }, []);

  const candidates = (data?.candidates ?? {}) as Record<string, Candidate>;
  const nowSeconds = freshnessNow;

  const rows = useMemo(
    () => Object.entries(candidates).sort(([leftSymbol, left], [rightSymbol, right]) => {
      const leftRank = left.score;
      const rightRank = right.score;
      if (typeof leftRank === "number" && typeof rightRank === "number" && leftRank !== rightRank) return rightRank - leftRank;
      if (typeof leftRank === "number") return -1;
      if (typeof rightRank === "number") return 1;
      return leftSymbol.localeCompare(rightSymbol);
    }),
    [candidates],
  );

  const freshnessSummary = useMemo(
    () => summarizeCandidateFreshness(candidates as Record<string, unknown>, freshnessNow),
    [candidates, freshnessNow],
  );

  // Extract signals (ENTRY_READY or ACTIVE)
  const signals = useMemo(() => {
    return rows.filter(([, c]) => {
      const dec = getDecision(c);
      return dec === "ENTRY_READY" || dec === "ACTIVE";
    });
  }, [rows]);

  const signalSymbols = useMemo(() => new Set(signals.map(([s]) => s)), [signals]);

  let emptyState = null;
  if (data === null) {
    emptyState = (
      <div className="mx-auto max-w-7xl px-6 py-16 text-center">
        <span className="live-dot mx-auto block" aria-hidden="true" />
        <p className="mt-4 text-lg font-medium">Initializing live state…</p>
        <p className="mt-2 text-sm text-slate-400">Waiting for stream snapshot.</p>
      </div>
    );
  }

  return (
    <main className="min-h-dvh pb-14 text-slate-100">
      {/* ─── Header ─── */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/85 backdrop-blur supports-[backdrop-filter]:bg-slate-950/70">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:h-16 sm:px-6 lg:px-8">
          <Activity className="shrink-0 text-emerald-400" size={22} aria-hidden="true" />
          <h1 className="truncate text-base font-bold tracking-tight sm:text-lg">WaterfallHunter</h1>
          <p className="hidden text-xs text-slate-400 sm:block">Calibrated signal terminal</p>
          <div className="ml-auto flex items-center gap-2">
            {generatedAt !== null && (
              <time dateTime={new Date(generatedAt).toISOString()} className="hidden font-mono text-xs text-slate-500 md:inline">
                {new Date(generatedAt).toLocaleTimeString()}
              </time>
            )}
            <span className={`status-pill border ${freshnessSummary.state === "fresh" ? "border-emerald-400/25 bg-emerald-500/10 text-emerald-200" : "border-amber-400/25 bg-amber-500/10 text-amber-200"}`}>
              <Clock3 size={13} />
              {freshnessSummary.fresh}/{freshnessSummary.total}
            </span>
            <span className={`status-pill border ${mode === "stream" ? "border-emerald-400/25 bg-emerald-500/10 text-emerald-200" : mode === "polling" ? "border-sky-400/25 bg-sky-500/10 text-sky-200" : "border-amber-400/25 bg-amber-500/10 text-amber-200"}`}>
              {mode === "stream" ? <Wifi size={13} /> : <WifiOff size={13} />}
              {connectionLabel(mode)}
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-6 px-4 pt-5 sm:px-6 lg:px-8">
        {emptyState}

        {data !== null && (
          <>
            {/* ─── 1. Signals Section (top) ─── */}
            {signals.length > 0 && (
              <section>
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-emerald-400">
                  <Zap size={16} /> Active Signals ({signals.length})
                </h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {signals.map(([symbol, candidate]) => (
                    <SignalCard key={symbol} symbol={symbol} candidate={candidate} nowSeconds={nowSeconds} />
                  ))}
                </div>
              </section>
            )}

            {/* ─── 2. Market Overview ─── */}
            <section>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-300">
                <Activity size={16} className="text-amber-400" /> Market Overview
              </h2>
              <MarketOverview candidates={candidates} />
            </section>

            {/* ─── 3. Top 5 Candidates ─── */}
            <TopCandidates rows={rows} excludeSymbols={signalSymbols} />

            {/* ─── 4. Decision Terminal (consolidated) ─── */}
            <section>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-300">
                <Target size={16} className="text-sky-400" /> Decision Terminal
              </h2>
              <CandidateTable candidates={candidates} nowSeconds={nowSeconds} />
              <div className="mt-4">
                <DecisionTerminal terminal={data.decision_terminal} candidates={candidates} nowSeconds={nowSeconds} />
              </div>
            </section>

            {/* ─── 5. Research & Diagnostics (collapsed) ─── */}
            <details className="rounded-xl border border-slate-800 bg-slate-950/30 overflow-hidden" open={researchOpen} onToggle={(e) => setResearchOpen(e.currentTarget.open)}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-semibold text-slate-300">
                <span className="flex items-center gap-2"><FlaskConical size={16} className="text-slate-400" /> Research & Diagnostics</span>
                <ChevronDown size={16} className={`transition-transform ${researchOpen ? "rotate-180" : ""}`} />
              </summary>
              {researchOpen && (
                <div className="border-t border-slate-800 px-4 py-5 sm:px-5 space-y-6">
                  <OutcomeEvidence />
                  <RecentSignals />
                  <HistoricalOutcomes />
                  <ProductionEvidence />
                  <FeatureReplay />
                  <LifecycleShadow />
                  <BacktestLab />
                  <SignalFunnel funnel={data?.signal_funnel as SignalFunnelData | undefined} />
                  <FinalRanking ranking={data?.final_ranking} />
                </div>
              )}
            </details>
          </>
        )}
      </div>
    </main>
  );
}
