"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, Wifi, WifiOff, Clock3, TrendingDown, TrendingUp, Zap, Target, ChevronDown, BarChart3, FlaskConical, Brain, DollarSign } from "lucide-react";
import { Candidate } from "@/components/score-card";
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

function boundedJitter(maximum: number): number {
  const sample = new Uint32Array(1);
  globalThis.crypto.getRandomValues(sample);
  return Math.floor((sample[0] / 0xffffffff) * maximum);
}

/* ─── Type helpers ─── */
function getMetrics(c: Candidate): Record<string, unknown> | undefined {
  const m = c.metrics;
  return m !== null && typeof m === "object" && !Array.isArray(m) ? m as Record<string, unknown> : undefined;
}
function getED(c: Candidate): Record<string, unknown> | undefined {
  const m = getMetrics(c);
  const ed = m?.entry_decision;
  return ed !== null && typeof ed === "object" && !Array.isArray(ed) ? ed as Record<string, unknown> : undefined;
}
function getReadiness(c: Candidate): number {
  const r = getED(c)?.entry_readiness;
  return typeof r === "number" && Number.isFinite(r) ? r : 0;
}
function getDecision(c: Candidate): string {
  return (getED(c)?.decision as string) ?? "—";
}
function getTradePlan(c: Candidate): Record<string, unknown> | null {
  const tp = getED(c)?.trade_plan;
  return tp !== null && typeof tp === "object" && !Array.isArray(tp) ? tp as Record<string, unknown> : null;
}
function getReasons(c: Candidate): string[] {
  const r = getED(c)?.reason_codes;
  return Array.isArray(r) ? r.filter((x): x is string => typeof x === "string") : [];
}

/* ─── Signal Card (clean, spacious) ─── */
function SignalCard({ symbol, candidate }: Readonly<{ symbol: string; candidate: Candidate }>) {
  const ed = getED(candidate);
  const tp = getTradePlan(candidate);
  if (!ed || !tp) return null;

  const ep = tp.entry_price as number | undefined;
  const sl = tp.stop_loss as number | undefined;
  const tp1 = tp.take_profit_1 as number | undefined;
  const tp2 = tp.take_profit_2 as number | undefined;
  const r2r = tp.reward_to_risk as number | undefined;
  const readiness = (ed.entry_readiness as number) ?? 0;
  const es = ed.evidence_summary as Record<string, unknown> | undefined;
  const cascade = es?.cascade as Record<string, unknown> | undefined;
  const cross = es?.cross_exchange_confirmed as boolean | undefined;
  const reasons = getReasons(candidate);
  const ai = getMetrics(candidate)?.ai_advisory as Record<string, unknown> | undefined;
  const aiAdvice = (ai?.ai_advice as string) ?? "—";
  const aiProvider = (ai?.ai_provider as string) ?? "none";

  const fmt = (v: number | undefined) => v !== undefined ? (v < 1 ? v.toFixed(6) : v < 100 ? v.toFixed(4) : v.toFixed(2)) : "—";
  const riskPct = ep && sl ? Math.abs((ep - sl) / ep * 100).toFixed(1) : "—";

  const aiColor = aiAdvice === "LONG" || aiAdvice === "GO" ? "text-emerald-400" : aiAdvice === "SHORT" || aiAdvice === "AVOID" ? "text-rose-400" : "text-amber-400";

  return (
    <div className="rounded-2xl border-2 border-emerald-500/20 bg-gradient-to-br from-emerald-950/40 to-slate-950 p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-500/20">
            <Zap size={18} className="text-emerald-400" />
          </div>
          <div>
            <span className="text-xl font-bold text-white">{symbol.replace("/USDT:USDT", "")}</span>
            <span className="ml-2 text-xs text-slate-500">{String(candidate.status ?? "—")}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold text-emerald-400">{readiness.toFixed(0)}<span className="text-xs text-slate-500">/100</span></div>
          <div className="text-[10px] uppercase text-slate-500">Readiness</div>
        </div>
      </div>

      {/* Trade Plan - large, clear */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="rounded-lg bg-sky-950/40 p-3 text-center">
          <div className="text-[10px] uppercase text-sky-400/70">Entry</div>
          <div className="font-mono text-base font-bold text-sky-300">{fmt(ep)}</div>
        </div>
        <div className="rounded-lg bg-rose-950/40 p-3 text-center">
          <div className="text-[10px] uppercase text-rose-400/70">Stop Loss</div>
          <div className="font-mono text-base font-bold text-rose-300">{fmt(sl)}</div>
        </div>
        <div className="rounded-lg bg-emerald-950/40 p-3 text-center">
          <div className="text-[10px] uppercase text-emerald-400/70">Take Profit</div>
          <div className="font-mono text-base font-bold text-emerald-300">{fmt(tp1)}</div>
        </div>
      </div>

      {/* Key metrics */}
      <div className="flex flex-wrap gap-2 text-xs">
        {tp2 !== undefined && tp2 !== null && <span className="rounded-full bg-slate-800/60 px-3 py-1 text-slate-300">TP2: {fmt(tp2)}</span>}
        {r2r !== undefined && <span className="rounded-full bg-slate-800/60 px-3 py-1 text-slate-300">R:R 1:{r2r}</span>}
        <span className="rounded-full bg-slate-800/60 px-3 py-1 text-slate-300">Risk: {riskPct}%</span>
        {cascade && <span className="rounded-full bg-slate-800/60 px-3 py-1 text-slate-300">Cascade: {String(cascade.status ?? "?")}</span>}
        {cross !== undefined && <span className={`rounded-full px-3 py-1 ${cross ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800/60 text-slate-400"}`}>Cross {cross ? "✓" : "—"}</span>}
        {aiAdvice !== "—" && (
          <span className={`rounded-full bg-slate-800/60 px-3 py-1 ${aiColor}`}>
            AI: {aiAdvice} {aiProvider !== "none" ? `(${aiProvider})` : ""}
          </span>
        )}
      </div>
    </div>
  );
}

/* ─── Market Overview (clean, minimal) ─── */
function MarketOverview({ candidates }: Readonly<{ candidates: Record<string, Candidate> }>) {
  const btc = candidates["BTC/USDT:USDT"];
  const eth = candidates["ETH/USDT:USDT"];
  const btcPrice = typeof btc?.last_price === "number" ? btc.last_price : undefined;
  const ethPrice = typeof eth?.last_price === "number" ? eth.last_price : undefined;

  const all = Object.values(candidates);
  const fuelRich = all.filter(c => c.status === "FUEL-RICH").length;
  const watch = all.filter(c => c.status === "WATCH").length;
  const bearish = fuelRich > watch;
  const entryReady = all.filter(c => getDecision(c) === "ENTRY_READY" || getDecision(c) === "ACTIVE").length;
  const forming = all.filter(c => getDecision(c) === "FORMING").length;

  const fmtPrice = (v: number | undefined) => {
    if (v === undefined) return "—";
    if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    if (v >= 1) return `$${v.toFixed(2)}`;
    return `$${v.toFixed(4)}`;
  };

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
      <div className="rounded-xl border border-amber-500/15 bg-amber-950/5 p-3">
        <div className="text-xs text-amber-400/60">BTC Price</div>
        <div className="mt-1 font-mono text-base font-bold text-amber-200">{fmtPrice(btcPrice)}</div>
      </div>
      <div className="rounded-xl border border-indigo-500/15 bg-indigo-950/5 p-3">
        <div className="text-xs text-indigo-400/60">ETH Price</div>
        <div className="mt-1 font-mono text-base font-bold text-indigo-200">{fmtPrice(ethPrice)}</div>
      </div>
      <div className="rounded-xl border border-slate-700/30 bg-slate-900/30 p-3">
        <div className="text-xs text-slate-400">Market</div>
        <div className={`mt-1 text-base font-bold ${bearish ? "text-rose-400" : "text-amber-400"}`}>
          {bearish ? "Bearish" : "Neutral"}
        </div>
      </div>
      <div className="rounded-xl border border-slate-700/30 bg-slate-900/30 p-3">
        <div className="text-xs text-slate-400">Tracked</div>
        <div className="mt-1 font-mono text-base font-bold text-slate-200">{all.length}</div>
      </div>
      <div className="rounded-xl border border-emerald-500/15 bg-emerald-950/5 p-3">
        <div className="text-xs text-emerald-400/60">Signals</div>
        <div className="mt-1 font-mono text-base font-bold text-emerald-300">{entryReady}</div>
      </div>
      <div className="rounded-xl border border-sky-500/15 bg-sky-950/5 p-3">
        <div className="text-xs text-sky-400/60">Forming</div>
        <div className="mt-1 font-mono text-base font-bold text-sky-300">{forming}</div>
      </div>
    </div>
  );
}

/* ─── Top Candidates (clean cards) ─── */
function TopCandidates({ rows, excludeSymbols }: Readonly<{ rows: [string, Candidate][]; excludeSymbols: Set<string> }>) {
  const top5 = rows
    .filter(([sym]) => !excludeSymbols.has(sym))
    .filter(([, c]) => getReadiness(c) > 0)
    .sort(([, a], [, b]) => getReadiness(b) - getReadiness(a))
    .slice(0, 5);

  if (top5.length === 0) return null;

  const decColor = (dec: string) =>
    dec === "ENTRY_READY" || dec === "ACTIVE" ? "text-emerald-400"
    : dec === "FORMING" ? "text-sky-400"
    : dec === "LATE" ? "text-amber-400" : "text-slate-400";

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
        <BarChart3 size={15} className="mr-2 inline text-sky-400" /> Top Candidates
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {top5.map(([symbol, candidate]) => {
          const r = getReadiness(candidate);
          const dec = getDecision(candidate);
          const tp = getTradePlan(candidate);
          const es = getED(candidate)?.evidence_summary as Record<string, unknown> | undefined;
          const cascade = es?.cascade as Record<string, unknown> | undefined;
          const cross = es?.cross_exchange_confirmed as boolean | undefined;
          const ai = getMetrics(candidate)?.ai_advisory as Record<string, unknown> | undefined;
          const aiAdvice = (ai?.ai_advice as string) ?? "";

          return (
            <div key={symbol} className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-white">{symbol.replace("/USDT:USDT", "")}</span>
                <span className={`text-xs font-semibold ${decColor(dec)}`}>{dec}</span>
              </div>
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-lg font-bold text-emerald-400">{r.toFixed(0)}</span>
                <span className="text-xs text-slate-500">{String(candidate.status ?? "—")}</span>
              </div>
              {tp && (
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between"><span className="text-slate-500">EP</span><span className="font-mono text-sky-300">{((tp.entry_price as number) ?? 0).toFixed(4)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">SL</span><span className="font-mono text-rose-300">{((tp.stop_loss as number) ?? 0).toFixed(4)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">TP1</span><span className="font-mono text-emerald-300">{((tp.take_profit_1 as number) ?? 0).toFixed(4)}</span></div>
                </div>
              )}
              <div className="mt-2 flex flex-wrap gap-1">
                {cross !== undefined && <span className={`rounded px-1.5 py-0.5 text-[10px] ${cross ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800/40 text-slate-500"}`}>Cross {cross ? "✓" : "—"}</span>}
                {cascade && <span className="rounded bg-slate-800/40 px-1.5 py-0.5 text-[10px] text-slate-500">{String(cascade.status ?? "?")}</span>}
                {aiAdvice && aiAdvice !== "—" && <span className="rounded bg-violet-500/10 px-1.5 py-0.5 text-[10px] text-violet-400">AI: {aiAdvice}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ─── Backtester Results Widget ─── */
function BacktesterResults() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const resp = await fetch("/dashboard/api/backtest/results");
        if (resp.ok) {
          const backendUrl = "http://172.19.0.2:8000";
          const r2 = await fetch(`${backendUrl}/api/backtest/results`);
          if (r2.ok) setData(await r2.json());
        }
      } catch { /* ignore */ }
      finally { setLoading(false); }
    };
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  if (loading && !data) return null;
  if (!data) return null;
  const stats = (data.stats ?? {}) as Record<string, unknown>;

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
        <DollarSign size={15} className="mr-2 inline text-amber-400" /> Backtester ($200 Capital)
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-3">
          <div className="text-xs text-slate-500">Capital</div>
          <div className="mt-1 font-mono font-bold text-amber-300">${Number(stats.current_capital ?? 200).toFixed(2)}</div>
        </div>
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-3">
          <div className="text-xs text-slate-500">Trades</div>
          <div className="mt-1 font-mono font-bold text-slate-200">{String(stats.total_trades ?? 0)}</div>
        </div>
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-3">
          <div className="text-xs text-slate-500">Win Rate</div>
          <div className="mt-1 font-mono font-bold text-emerald-400">{Number(stats.win_rate ?? 0).toFixed(1)}%</div>
        </div>
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-3">
          <div className="text-xs text-slate-500">Max DD</div>
          <div className="mt-1 font-mono font-bold text-rose-400">{Number(stats.max_drawdown_pct ?? 0).toFixed(1)}%</div>
        </div>
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-3">
          <div className="text-xs text-slate-500">Profit Factor</div>
          <div className="mt-1 font-mono font-bold text-sky-300">{Number(stats.profit_factor ?? 0).toFixed(2)}</div>
        </div>
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-3">
          <div className="text-xs text-slate-500">Sharpe</div>
          <div className="mt-1 font-mono font-bold text-violet-300">{Number(stats.sharpe_ratio ?? 0).toFixed(2)}</div>
        </div>
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
    const t = setInterval(() => setFreshnessNow(Date.now() / 1000), 5000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    let active = true;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let pollAttempt = 0;
    let streaming = false;
    let hasSnapshot = false;
    let watchdog: ReturnType<typeof setInterval> | undefined;
    const stream = new EventSource("/dashboard/api/stream");

    const accept = (snapshot: DashboardSnapshot) => {
      if (!active || snapshot.snapshot_version <= latestVersion.current) return;
      latestVersion.current = snapshot.snapshot_version;
      hasSnapshot = true;
      setData(snapshot);
      setGeneratedAt(snapshot.generated_at * 1000);
    };

    const schedulePoll = (delay: number) => {
      if (!active || pollTimer !== undefined) return;
      pollTimer = setTimeout(() => {
        pollTimer = undefined;
        if (!active) return;
        void (async () => {
          try {
            const resp = await fetch("/dashboard/api/candidates", { cache: "no-store" });
            const snap = resp.ok ? dashboardSnapshot(await resp.json()) : undefined;
            if (!snap) throw new Error("bad snapshot");
            accept(snap);
            pollAttempt = 0;
            if (streaming) return;
            setMode("polling");
            schedulePoll(5000);
          } catch {
            pollAttempt++;
            if (!streaming) setMode("reconnecting");
            if (!streaming || !hasSnapshot) schedulePoll(Math.min(30000, 1000 * 2 ** Math.min(pollAttempt, 5)));
          }
        })();
      }, delay + (delay > 0 ? boundedJitter(1500) : 0));
    };

    const onMsg = (ev: MessageEvent<string>) => {
      try {
        const pkt = dashboardStreamEvent(JSON.parse(ev.data));
        if (!pkt) throw new Error("bad");
        if (pkt.payload) { accept(pkt.payload); if (hasSnapshot && pollTimer) { clearTimeout(pollTimer); pollTimer = undefined; } }
        lastStreamEventAt.current = Date.now();
        streaming = true;
        setMode("stream");
      } catch { streaming = false; setMode("reconnecting"); schedulePoll(1000); }
    };

    stream.onopen = () => { pollAttempt = 0; if (!hasSnapshot) setMode("reconnecting"); };
    stream.onerror = () => { streaming = false; setMode("reconnecting"); schedulePoll(1000); };
    stream.onmessage = onMsg;
    stream.addEventListener("snapshot", (e) => e instanceof MessageEvent && onMsg(e as MessageEvent<string>));
    stream.addEventListener("heartbeat", (e) => e instanceof MessageEvent && onMsg(e as MessageEvent<string>));
    schedulePoll(0);
    watchdog = setInterval(() => {
      if (!active || !streaming || lastStreamEventAt.current <= 0) return;
      if (Date.now() - lastStreamEventAt.current > 45000) { streaming = false; setMode("reconnecting"); schedulePoll(0); }
    }, 5000);

    return () => {
      active = false;
      stream.close();
      if (pollTimer) clearTimeout(pollTimer);
      if (watchdog) clearInterval(watchdog);
    };
  }, []);

  const candidates = (data?.candidates ?? {}) as Record<string, Candidate>;
  const nowSeconds = freshnessNow;

  const rows = useMemo(
    () => Object.entries(candidates).sort(([, a], [, b]) => {
      const ra = typeof a.score === "number" ? a.score : -1;
      const rb = typeof b.score === "number" ? b.score : -1;
      return rb - ra;
    }),
    [candidates],
  );

  const freshnessSummary = useMemo(
    () => summarizeCandidateFreshness(candidates as Record<string, unknown>, freshnessNow),
    [candidates, freshnessNow],
  );

  const signals = useMemo(() => rows.filter(([, c]) => {
    const d = getDecision(c);
    return d === "ENTRY_READY" || d === "ACTIVE";
  }), [rows]);

  const signalSymbols = useMemo(() => new Set(signals.map(([s]) => s)), [signals]);

  return (
    <main className="min-h-dvh bg-slate-950 pb-14 text-slate-100">
      {/* ─── Header (clean, minimal) ─── */}
      <header className="sticky top-0 z-40 border-b border-slate-800/50 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/15">
            <Activity size={18} className="text-emerald-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">WaterfallHunter</h1>
            <p className="text-xs text-slate-500">Signal Terminal · Calibrated</p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {generatedAt !== null && (
              <time className="hidden font-mono text-xs text-slate-600 md:inline">
                {new Date(generatedAt).toLocaleTimeString()}
              </time>
            )}
            <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${freshnessSummary.state === "fresh" ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300"}`}>
              <Clock3 size={12} />
              {freshnessSummary.fresh}/{freshnessSummary.total}
            </span>
            <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${mode === "stream" ? "bg-emerald-500/10 text-emerald-300" : mode === "polling" ? "bg-sky-500/10 text-sky-300" : "bg-amber-500/10 text-amber-300"}`}>
              {mode === "stream" ? <Wifi size={12} /> : <WifiOff size={12} />}
              {mode === "stream" ? "Live" : mode === "polling" ? "Polling" : "Reconnecting"}
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-8 px-6 pt-6">
        {data === null ? (
          <div className="flex min-h-[400px] flex-col items-center justify-center text-center">
            <div className="mb-3 h-3 w-3 animate-pulse rounded-full bg-emerald-400" />
            <p className="text-lg font-medium text-slate-300">Initializing live state…</p>
            <p className="mt-1 text-sm text-slate-600">Waiting for stream snapshot</p>
          </div>
        ) : (
          <>
            {/* ─── 1. Active Signals ─── */}
            {signals.length > 0 && (
              <section>
                <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-emerald-400">
                  <Zap size={16} /> Active Signals ({signals.length})
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {signals.map(([symbol, candidate]) => (
                    <SignalCard key={symbol} symbol={symbol} candidate={candidate} />
                  ))}
                </div>
              </section>
            )}

            {/* ─── 2. Market Overview ─── */}
            <section>
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
                <Activity size={15} className="mr-2 inline text-amber-400" /> Market Overview
              </h2>
              <MarketOverview candidates={candidates} />
            </section>

            {/* ─── 3. Top 5 Candidates ─── */}
            <TopCandidates rows={rows} excludeSymbols={signalSymbols} />

            {/* ─── 4. Backtester Results ─── */}
            <BacktesterResults />

            {/* ─── 5. Decision Terminal ─── */}
            <section>
              <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
                <Target size={15} className="mr-2 inline text-sky-400" /> Decision Terminal
              </h2>
              <CandidateTable candidates={candidates} nowSeconds={nowSeconds} />
              <div className="mt-4">
                <DecisionTerminal terminal={data.decision_terminal} candidates={candidates} nowSeconds={nowSeconds} />
              </div>
            </section>

            {/* ─── 6. Research & Diagnostics (collapsed) ─── */}
            <details className="rounded-xl border border-slate-800/50 bg-slate-950/30 overflow-hidden" open={researchOpen} onToggle={(e) => setResearchOpen(e.currentTarget.open)}>
              <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 text-sm font-semibold text-slate-400">
                <span className="flex items-center gap-2"><FlaskConical size={15} /> Research & Diagnostics</span>
                <ChevronDown size={16} className={`transition-transform ${researchOpen ? "rotate-180" : ""}`} />
              </summary>
              {researchOpen && (
                <div className="border-t border-slate-800/50 px-5 py-5 space-y-6">
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
