"use client";

import { useEffect, useState, useCallback } from "react";

// ── Types ─────────────────────────────────────────────────────────────────

interface AgentTask {
  name: string;
  status: string;
  progress_percent: number;
  checklist_total: number;
  checklist_done: number;
  stale?: boolean;
}
interface BacklogItem { title: string; tag: string; }
interface NeedItem    { title: string; ask: string; tag: string; }
interface CronJob     { name: string; health: string; errors: number; lastRunAgo?: string; stale?: boolean; }
interface CronData    { healthy: number; erroring: number; total: number; jobs: CronJob[]; }
interface AgentData   {
  status: "working" | "recent" | "idle" | "offline";
  last_active_ago: string;
  active_task: AgentTask;
  backlog: BacklogItem[];
  done: string[];
  cron?: CronData;
  cron_alerts?: { name: string; errors: number }[];
}
interface WJPData     { from_kikai: NeedItem[]; from_yama: NeedItem[]; resolved: {title: string; resolution: string}[]; }
interface YourMove    { priority: string; title: string; ask: string; }
interface DashboardData {
  timestamp_ms: number;
  collected_at: string;
  your_move: YourMove;
  kikai: AgentData;
  yama:  AgentData;
  wjp:   WJPData;
}
interface Intel { generated_at: string; items: string[]; }

// ── Helpers ───────────────────────────────────────────────────────────────

function timeAgo(ts: string | number | null): string {
  if (!ts) return "never";
  const ms = typeof ts === "number" ? ts : new Date(ts).getTime();
  const diff = Date.now() - ms;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const TAG_STYLES: Record<string, {bg: string; text: string}> = {
  "needs-you":  { bg: "rgba(255,68,68,0.15)",  text: "#FF6666" },
  "deep-work":  { bg: "rgba(0,217,255,0.12)",  text: "#00D9FF" },
  "for-crypto": { bg: "rgba(147,51,234,0.15)", text: "#c4b5fd" },
  "blocking":   { bg: "rgba(255,68,68,0.15)",  text: "#FF6666" },
  "enabling":   { bg: "rgba(255,215,0,0.15)",  text: "#FFD700" },
  "signal":     { bg: "rgba(136,136,136,0.15)","text": "#999"  },
};

const STATUS_CONFIG = {
  working: { color: "#39FF14", label: "working", pulse: true },
  recent:  { color: "#00D9FF", label: "recent",  pulse: false },
  idle:    { color: "#444",    label: "idle",     pulse: false },
  offline: { color: "#FF4444", label: "offline",  pulse: false },
};

function Tag({ label }: { label: string }) {
  const s = TAG_STYLES[label] || { bg: "rgba(136,136,136,0.15)", text: "#888" };
  return <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, background: s.bg, color: s.text, fontWeight: 600, whiteSpace: "nowrap", flexShrink: 0 }}>{label}</span>;
}

function Ring({ pct, stale }: { pct: number; stale?: boolean }) {
  const color = stale ? "#FF4444" : pct === 100 ? "#39FF14" : pct > 60 ? "#00D9FF" : pct > 30 ? "#FFD700" : "#FF6B35";
  const r = 22, circ = 2 * Math.PI * r;
  return (
    <div style={{ width: 56, height: 56, position: "relative", flexShrink: 0 }}>
      <svg width="56" height="56" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="28" cy="28" r={r} fill="none" stroke="#1a1a1a" strokeWidth="4" />
        <circle cx="28" cy="28" r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={`${(pct / 100) * circ} ${circ}`}
          style={{ transition: "stroke-dasharray 0.5s ease", filter: pct > 0 ? `drop-shadow(0 0 4px ${color}66)` : "none" }} />
      </svg>
      <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, color }}>{stale ? "!" : `${pct}%`}</span>
    </div>
  );
}

function StatusDot({ status }: { status: "working" | "recent" | "idle" | "offline" }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.idle;
  return (
    <div style={{ position: "relative", width: 10, height: 10, flexShrink: 0 }}>
      {cfg.pulse && (
        <div style={{
          position: "absolute", inset: -4, borderRadius: "50%",
          background: cfg.color, opacity: 0.25,
          animation: "ping 1.5s cubic-bezier(0,0,0.2,1) infinite"
        }} />
      )}
      <div style={{ width: 10, height: 10, borderRadius: "50%", background: cfg.color,
        boxShadow: cfg.pulse ? `0 0 8px ${cfg.color}` : "none", position: "relative" }} />
    </div>
  );
}

// ── Card Components ───────────────────────────────────────────────────────

function ActiveTaskCard({ task, color }: { task: AgentTask; color: string }) {
  const isStale = task.stale || task.status === "STALE";
  const isActive = task.status === "IN_PROGRESS";
  const statusColor = isStale ? "#FF4444" : isActive ? color : "#444";
  const statusLabel = isStale ? "⚠ STALE" : task.status;

  return (
    <div style={{ background: "#111", border: `1px solid ${isStale ? "#FF444433" : color + "22"}`,
      borderTop: `3px solid ${isStale ? "#FF4444" : color}`, borderRadius: 12, padding: "20px" }}>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <Ring pct={task.progress_percent} stale={isStale} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: isStale ? "#FF6666" : "#e5e5e5",
            lineHeight: 1.4, marginBottom: 8 }}>{task.name}</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <span style={{ fontSize: 12, padding: "2px 8px", borderRadius: 99,
              background: `${statusColor}18`, color: statusColor,
              border: `1px solid ${statusColor}33`, fontWeight: 600 }}>
              {statusLabel}
            </span>
            {task.checklist_total > 0 && (
              <span style={{ fontSize: 12, color: "#444" }}>{task.checklist_done}/{task.checklist_total} steps</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function BacklogCard({ item }: { item: BacklogItem }) {
  return (
    <div style={{ background: "#0f0f0f", border: "1px solid #1e1e1e", borderRadius: 10,
      padding: "12px 16px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
      <span style={{ fontSize: 13, color: "#bbb", lineHeight: 1.4, flex: 1 }}>{item.title}</span>
      <Tag label={item.tag} />
    </div>
  );
}

function DoneCard({ text }: { text: string }) {
  return (
    <div style={{ background: "#0a0a0a", border: "1px solid #1a1a1a",
      borderLeft: "3px solid #39FF1433", borderRadius: 10, padding: "11px 14px" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
        <span style={{ color: "#39FF1466", fontSize: 12, flexShrink: 0, marginTop: 2 }}>✓</span>
        <span style={{ fontSize: 13, color: "#555", lineHeight: 1.4 }}>{text}</span>
      </div>
    </div>
  );
}

function NeedCard({ item }: { item: NeedItem }) {
  const s = TAG_STYLES[item.tag] || TAG_STYLES["signal"];
  return (
    <div style={{ background: "#0f0f0f", border: `1px solid ${s.text}22`,
      borderLeft: `3px solid ${s.text}`, borderRadius: 10, padding: "14px 18px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Tag label={item.tag} />
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, color: "#ddd", marginBottom: item.ask ? 6 : 0, lineHeight: 1.4 }}>{item.title}</div>
      {item.ask && <div style={{ fontSize: 12, color: "#555", lineHeight: 1.5 }}>{item.ask}</div>}
    </div>
  );
}

function CronHealthBar({ cron, alerts }: { cron?: CronData; alerts?: {name:string;errors:number}[] }) {
  if (!cron) return null;
  const hasErrors = cron.erroring > 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ fontSize: 11, color: hasErrors ? "#FF6666" : "#444", fontWeight: 600 }}>
        {hasErrors ? `⚠ ${cron.erroring} cron error${cron.erroring > 1 ? "s" : ""}` : `${cron.healthy}/${cron.total} crons ok`}
      </span>
      {alerts?.map((a, i) => (
        <span key={i} style={{ fontSize: 10, padding: "1px 6px", borderRadius: 99,
          background: "rgba(255,68,68,0.12)", color: "#FF6666", border: "1px solid rgba(255,68,68,0.2)" }}>
          {a.name}
        </span>
      ))}
    </div>
  );
}

// ── Agent Row ─────────────────────────────────────────────────────────────

function AgentRow({ name, color, emoji, data }: { name: string; color: string; emoji: string; data: AgentData }) {
  const cfg = STATUS_CONFIG[data.status] || STATUS_CONFIG.idle;
  return (
    <div style={{ background: "#0d0d0d", border: "1px solid #1a1a1a", borderRadius: 16, overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "14px 24px", borderBottom: "1px solid #1a1a1a",
        display: "flex", alignItems: "center", gap: 12,
        background: `linear-gradient(90deg, ${color}0a, transparent)` }}>
        <StatusDot status={data.status} />
        <span style={{ fontSize: 16, fontWeight: 700, color: "#e5e5e5" }}>{emoji} {name}</span>
        <span style={{ fontSize: 12, color: cfg.color, fontWeight: 500 }}>· {cfg.label}</span>
        <span style={{ fontSize: 12, color: "#555" }}>· {data.last_active_ago}</span>
        <div style={{ marginLeft: "auto" }}>
          <CronHealthBar cron={data.cron} alerts={data.cron_alerts} />
        </div>
      </div>

      {/* Columns */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr" }}>
        {[
          { label: "Backlog", count: data.backlog.length,
            content: <>{data.backlog.length ? data.backlog.map((item, i) => <BacklogCard key={i} item={item} />) : <EmptyCol text="nothing queued" />}</> },
          { label: "In Progress", count: 1,
            content: <ActiveTaskCard task={data.active_task} color={color} /> },
          { label: "Done", count: data.done.length,
            content: <>{data.done.map((t, i) => <DoneCard key={i} text={t} />)}</> },
        ].map((col, ci) => (
          <div key={col.label} style={{ padding: "18px 20px", borderRight: ci < 2 ? "1px solid #161616" : "none" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: "#333", textTransform: "uppercase", letterSpacing: "0.1em" }}>{col.label}</span>
              <span style={{ fontSize: 11, color: "#444", background: "#161616",
                border: "1px solid #282828", borderRadius: 99, padding: "1px 7px" }}>{col.count}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>{col.content}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyCol({ text }: { text: string }) {
  return <div style={{ fontSize: 12, color: "#333", padding: "12px 0" }}>{text}</div>;
}

// ── WJP Row ───────────────────────────────────────────────────────────────

function WJPRow({ data }: { data: WJPData }) {
  const totalOpen = data.from_kikai.length + data.from_yama.length;
  const cols = [
    { label: "From Kikai", count: data.from_kikai.length, items: data.from_kikai },
    { label: "From Yama",  count: data.from_yama.length,  items: data.from_yama },
    { label: "Resolved",   count: data.resolved.length,   items: [] as NeedItem[], resolved: data.resolved },
  ];
  return (
    <div style={{ background: "#0d0d0d", border: "1px solid #FFD70022", borderRadius: 16, overflow: "hidden" }}>
      <div style={{ padding: "14px 24px", borderBottom: "1px solid #FFD70015",
        display: "flex", alignItems: "center", gap: 12,
        background: "linear-gradient(90deg, rgba(255,215,0,0.06), transparent)" }}>
        <div style={{ width: 10, height: 10, borderRadius: 99, background: "#FFD700",
          boxShadow: totalOpen > 0 ? "0 0 8px #FFD70088" : "none" }} />
        <span style={{ fontSize: 16, fontWeight: 700, color: "#e5e5e5" }}>👤 WJP</span>
        <span style={{ fontSize: 12, color: totalOpen > 0 ? "#FFD700" : "#444" }}>
          · {totalOpen > 0 ? `${totalOpen} item${totalOpen > 1 ? "s" : ""} need your call` : "all clear"}
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr" }}>
        {cols.map((col, ci) => (
          <div key={col.label} style={{ padding: "18px 20px", borderRight: ci < 2 ? "1px solid #161616" : "none" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: "#333", textTransform: "uppercase", letterSpacing: "0.1em" }}>{col.label}</span>
              <span style={{ fontSize: 11, color: "#2a2a2a", background: "#161616",
                border: "1px solid #222", borderRadius: 99, padding: "1px 7px" }}>{col.count}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {col.items.map((item, i) => <NeedCard key={i} item={item} />)}
              {col.resolved?.map((item, i) => (
                <div key={i} style={{ background: "#0a0a0a", border: "1px solid #1a1a1a",
                  borderLeft: "3px solid #39FF1433", borderRadius: 10, padding: "11px 14px" }}>
                  <div style={{ fontSize: 13, color: "#777", marginBottom: 2 }}>{item.title}</div>
                  <div style={{ fontSize: 11, color: "#444" }}>{item.resolution}</div>
                </div>
              ))}
              {col.items.length === 0 && !col.resolved?.length && (
                <div style={{ fontSize: 12, color: "#333", padding: "12px 0" }}>nothing here</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Top Cards ─────────────────────────────────────────────────────────────

function YourMoveCard({ move }: { move: YourMove }) {
  const accent = move.priority === "blocking" ? "#FF4444" : move.priority === "enabling" ? "#FFD700" : "#00D9FF";
  const label  = move.priority === "blocking" ? "🔴 Act first" : move.priority === "enabling" ? "🟠 Next up" : "⚡ Your move";
  return (
    <div style={{ background: "#0f0f0f", border: `1px solid ${accent}28`,
      borderLeft: `4px solid ${accent}`, borderRadius: 14, padding: "20px 24px" }}>
      <div style={{ fontSize: 11, color: accent, textTransform: "uppercase",
        letterSpacing: "0.1em", marginBottom: 10, fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: 19, fontWeight: 700, color: "#fff", marginBottom: 8, lineHeight: 1.3 }}>{move.title}</div>
      {move.ask && <div style={{ fontSize: 14, color: "#666", lineHeight: 1.6 }}>{move.ask}</div>}
    </div>
  );
}

function IntelCard({ intel }: { intel: Intel | null }) {
  return (
    <div style={{ background: "#0f0f0f", border: "1px solid #1a1a1a", borderRadius: 14, padding: "20px 24px" }}>
      <div style={{ fontSize: 11, color: "#FFD700", textTransform: "uppercase",
        letterSpacing: "0.1em", marginBottom: 14, fontWeight: 700 }}>
        📡 Intel {intel ? `· ${timeAgo(intel.generated_at)}` : "· refreshes at 7 AM"}
      </div>
      {intel?.items?.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {intel.items.map((item, i) => (
            <div key={i} style={{ display: "flex", gap: 10 }}>
              <span style={{ color: "#FFD700", fontSize: 13, flexShrink: 0, marginTop: 3 }}>›</span>
              <span style={{ fontSize: 13, color: "#777", lineHeight: 1.6 }}>{item}</span>
            </div>
          ))}
        </div>
      ) : (
        <span style={{ fontSize: 13, color: "#2a2a2a" }}>No intel yet</span>
      )}
    </div>
  );
}

function CronPanel({ jobs }: { jobs: CronJob[] }) {
  const errors = jobs.filter(j => j.health === "error");
  const stale = jobs.filter(j => j.stale);
  const [open, setOpen] = useState(errors.length > 0); // auto-expand if errors
  if (!errors.length && !stale.length) return null;

  return (
    <div style={{ background: "#0d0d0d", border: "1px solid #FF444422", borderLeft: "3px solid #FF4444",
      borderRadius: 12, padding: "14px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
           onClick={() => setOpen(!open)}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "#FF6666" }}>⚠ Cron Alerts</span>
        <span style={{ fontSize: 12, color: "#FF444488" }}>
          {errors.length} error{errors.length !== 1 ? "s" : ""}{stale.length ? `, ${stale.length} stale` : ""}
        </span>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#444" }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          {[...errors, ...stale].map((j, i) => (
            <div key={i} style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <span style={{ fontSize: 11, color: j.health === "error" ? "#FF6666" : "#FFD700" }}>
                {j.health === "error" ? "●" : "○"}
              </span>
              <span style={{ fontSize: 12, color: "#888" }}>{j.name}</span>
              {j.errors > 0 && <span style={{ fontSize: 11, color: "#FF444488" }}>{j.errors} errors</span>}
              {j.stale && <span style={{ fontSize: 11, color: "#FFD70088" }}>stale</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [data, setData]   = useState<DashboardData | null>(null);
  const [intel, setIntel] = useState<Intel | null>(null);
  const [lastSync, setLastSync] = useState(Date.now());

  const loadData = useCallback(async () => {
    const t = Date.now();
    try {
      const [dr, ir] = await Promise.all([
        fetch(`/data.json?t=${t}`),
        fetch(`/intel.json?t=${t}`)
      ]);
      if (dr.ok) setData(await dr.json());
      if (ir.ok) setIntel(await ir.json());
      setLastSync(Date.now());
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 30000); // 30s refresh
    return () => clearInterval(iv);
  }, [loadData]);

  if (!data) return (
    <div style={{ minHeight: "100vh", background: "#080808", display: "flex",
      alignItems: "center", justifyContent: "center" }}>
      <span style={{ color: "#333", fontSize: 15 }}>Loading...</span>
    </div>
  );

  const cronJobs = data.kikai.cron?.jobs || [];

  return (
    <>
      <style>{`
        @keyframes ping {
          75%, 100% { transform: scale(2); opacity: 0; }
        }
        @keyframes pulse-ring {
          0% { transform: scale(0.9); opacity: 0.5; }
          50% { transform: scale(1.1); opacity: 0.8; }
          100% { transform: scale(0.9); opacity: 0.5; }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #080808; }
      `}</style>

      <div style={{ minHeight: "100vh", background: "#080808", color: "#e5e5e5",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>

        {/* Top bar */}
        <div style={{ borderBottom: "1px solid #111", padding: "12px 32px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          position: "sticky", top: 0, background: "#080808", zIndex: 100, backdropFilter: "blur(10px)" }}>
          <h1 style={{ fontSize: 15, fontWeight: 800, margin: 0, letterSpacing: "-0.3px" }}>
            <span style={{ color: "#00D9FF" }}>Mission</span>{" "}
            <span style={{ color: "#555" }}>Control</span>
          </h1>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ fontSize: 12, color: "#555" }}>data {timeAgo(data.timestamp_ms)}</span>
            <span style={{ fontSize: 12, color: "#333" }}>synced {timeAgo(lastSync)}</span>
          </div>
        </div>

        <div style={{ padding: "20px 32px", display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Your Move + Intel */}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
            <YourMoveCard move={data.your_move} />
            <IntelCard intel={intel} />
          </div>

          {/* Cron alerts panel (only when errors) */}
          {cronJobs.some(j => j.health === "error" || j.stale) && (
            <CronPanel jobs={cronJobs} />
          )}

          {/* WJP row */}
          <WJPRow data={data.wjp} />

          {/* Kikai row */}
          <AgentRow name="Kikai" color="#00D9FF" emoji="🦊" data={data.kikai} />

          {/* Yama row */}
          <AgentRow name="Yama" color="#a78bfa" emoji="⚡" data={data.yama} />

        </div>

        <div style={{ textAlign: "center", padding: "8px 0 24px", fontSize: 11, color: "#1a1a1a" }}>
          auto-refresh 30s
        </div>
      </div>
    </>
  );
}
