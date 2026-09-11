"use client";

import { PointerEvent, useEffect, useMemo, useRef, useState } from "react";

export type GraphNode = {
  name: string;
  thai?: string;
  kind?: string;
  definition?: string;
};

export type GraphLink = {
  from: string;
  to: string;
  type?: string;
  label?: string;
};

export type GraphOverview = {
  nodes: GraphNode[];
  links: GraphLink[];
  skipped?: boolean;
};

type SimNode = GraphNode & {
  x: number;
  y: number;
  vx: number;
  vy: number;
};

type Point = { x: number; y: number };

const KIND_COLORS: Record<string, string> = {
  disease: "#c24e1d",
  concept: "#3d6b8c",
  prefix: "#7a5c2e",
  suffix: "#7a5c2e",
  symptom: "#c47a2c",
  sign: "#b86b2a",
  procedure: "#5a6b3d",
  abbreviation: "#6b4c7a",
};

function kindColor(kind?: string) {
  return KIND_COLORS[kind || ""] || "#8a6a4a";
}

function kindLabel(kind?: string) {
  const labels: Record<string, string> = {
    disease: "โรค",
    concept: "แนวคิด",
    prefix: "อุปสรรค",
    suffix: "ปัจจัย",
    symptom: "อาการ",
    sign: "อาการแสดง",
    procedure: "หัตถการ",
    abbreviation: "คำย่อ",
  };
  return labels[kind || ""] || kind || "ศัพท์";
}

function shortName(name: string) {
  return name.length > 18 ? `${name.slice(0, 16)}…` : name;
}

function runLayout(nodes: GraphNode[], links: GraphLink[], width: number, height: number): SimNode[] {
  const cx = width / 2;
  const cy = height / 2;
  const sim: SimNode[] = nodes.map((node, index) => {
    const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
    const radius = Math.min(width, height) * 0.34;
    return {
      ...node,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
    };
  });
  const byName = new Map(sim.map((node) => [node.name, node]));
  const edges = links
    .map((link) => {
      const a = byName.get(link.from);
      const b = byName.get(link.to);
      return a && b && a !== b ? { a, b } : null;
    })
    .filter((item): item is { a: SimNode; b: SimNode } => item !== null);

  const n = Math.max(sim.length, 1);
  const repulsion = 1800 + n * 28;
  const rest = Math.max(70, Math.min(130, 520 / Math.sqrt(n)));

  for (let step = 0; step < 160; step += 1) {
    for (let i = 0; i < sim.length; i += 1) {
      for (let j = i + 1; j < sim.length; j += 1) {
        const a = sim[i];
        const b = sim[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let dist = Math.hypot(dx, dy) || 0.01;
        const force = repulsion / (dist * dist);
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        a.vx += dx;
        a.vy += dy;
        b.vx -= dx;
        b.vy -= dy;
      }
    }
    for (const { a, b } of edges) {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const pull = (dist - rest) * 0.035;
      const fx = (dx / dist) * pull;
      const fy = (dy / dist) * pull;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }
    for (const node of sim) {
      node.vx += (cx - node.x) * 0.012;
      node.vy += (cy - node.y) * 0.012;
      node.vx *= 0.78;
      node.vy *= 0.78;
      node.x += node.vx;
      node.y += node.vy;
      node.x = Math.max(36, Math.min(width - 36, node.x));
      node.y = Math.max(28, Math.min(height - 28, node.y));
    }
  }
  return sim;
}

export function factsToGraph(
  facts: Array<{
    name: string;
    thai?: string;
    kind?: string;
    definition?: string;
    relation?: string;
    related_name?: string;
    related_thai?: string;
    related_definition?: string;
  }>,
): GraphOverview {
  const nodes = new Map<string, GraphNode>();
  const links: GraphLink[] = [];
  for (const fact of facts) {
    nodes.set(fact.name, {
      name: fact.name,
      thai: fact.thai,
      kind: fact.kind,
      definition: fact.definition,
    });
    if (!fact.related_name) continue;
    if (!nodes.has(fact.related_name)) {
      nodes.set(fact.related_name, {
        name: fact.related_name,
        thai: fact.related_thai,
        definition: fact.related_definition,
      });
    }
    const match = fact.relation?.match(/-\[(.+)\]->/);
    const outgoing = !fact.relation || fact.relation.startsWith(fact.name);
    links.push({
      from: outgoing ? fact.name : fact.related_name,
      to: outgoing ? fact.related_name : fact.name,
      label: match?.[1] || "เกี่ยวข้อง",
    });
  }
  return { nodes: [...nodes.values()], links };
}

export default function GraphView({
  graph,
  compact = false,
  highlight = [],
}: {
  graph: GraphOverview;
  compact?: boolean;
  highlight?: string[];
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 640, height: compact ? 260 : 520 });
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const dragRef = useRef<{ name: string; dx: number; dy: number } | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => {
      const next = {
        width: Math.max(320, el.clientWidth),
        height: Math.max(compact ? 220 : 420, el.clientHeight),
      };
      setSize((prev) =>
        prev.width === next.width && prev.height === next.height ? prev : next,
      );
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, [compact]);

  const nodeKey = graph.nodes.map((node) => node.name).join("|");
  const linkKey = graph.links.map((link) => `${link.from}->${link.to}`).join("|");

  useEffect(() => {
    const laid = runLayout(graph.nodes, graph.links, size.width, size.height);
    setPositions(Object.fromEntries(laid.map((node) => [node.name, { x: node.x, y: node.y }])));
    setSelected(null);
  }, [nodeKey, linkKey, size.width, size.height, graph.nodes, graph.links]);

  const degree = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of graph.nodes) counts.set(node.name, 0);
    for (const link of graph.links) {
      counts.set(link.from, (counts.get(link.from) || 0) + 1);
      counts.set(link.to, (counts.get(link.to) || 0) + 1);
    }
    return counts;
  }, [graph.nodes, graph.links]);

  const neighbors = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const node of graph.nodes) map.set(node.name, new Set());
    for (const link of graph.links) {
      map.get(link.from)?.add(link.to);
      map.get(link.to)?.add(link.from);
    }
    return map;
  }, [graph.nodes, graph.links]);

  const selectedNode = graph.nodes.find((node) => node.name === selected);
  const active = selected || hover;
  const focusSet = useMemo(() => {
    if (!active) return new Set(highlight);
    return new Set([active, ...(neighbors.get(active) || [])]);
  }, [active, neighbors, highlight]);

  function pointOf(name: string): Point {
    return positions[name] || { x: size.width / 2, y: size.height / 2 };
  }

  function onPointerDown(event: PointerEvent<SVGCircleElement>, name: string) {
    const point = pointOf(name);
    const rect = wrapRef.current?.getBoundingClientRect();
    dragRef.current = {
      name,
      dx: event.clientX - (rect?.left || 0) - point.x,
      dy: event.clientY - (rect?.top || 0) - point.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setSelected(name);
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!dragRef.current) return;
    const rect = wrapRef.current?.getBoundingClientRect();
    const x = Math.max(28, Math.min(size.width - 28, event.clientX - (rect?.left || 0) - dragRef.current.dx));
    const y = Math.max(22, Math.min(size.height - 22, event.clientY - (rect?.top || 0) - dragRef.current.dy));
    const name = dragRef.current.name;
    setPositions((prev) => ({ ...prev, [name]: { x, y } }));
  }

  function onPointerUp() {
    dragRef.current = null;
  }

  const kinds = [...new Set(graph.nodes.map((node) => node.kind).filter(Boolean))] as string[];

  return (
    <div className="flex h-full min-h-0 flex-col">
      {!compact && (
        <input
          value={query}
          onChange={(event) => {
            const value = event.target.value;
            setQuery(value);
            const match = graph.nodes.find((node) => {
              const q = value.trim().toLowerCase();
              return (
                node.name.toLowerCase() === q ||
                node.name.toLowerCase().includes(q) ||
                (node.thai || "").toLowerCase().includes(q)
              );
            });
            if (value.trim() && match) setSelected(match.name);
          }}
          placeholder="ค้นหา เช่น Hypertension"
          className="mb-3 w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
        />
      )}
      <div
        ref={wrapRef}
        className={`relative min-h-0 overflow-hidden rounded-2xl border border-[var(--line)] bg-[#fffaf1] ${
          compact ? "h-64" : "flex-1"
        }`}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${size.width} ${size.height}`}
          className="block h-full w-full touch-none"
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
          onClick={(event) => {
            if (event.target === event.currentTarget) setSelected(null);
          }}
        >
          <defs>
            <marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto">
              <path d="M0,1 L8,4 L0,7 Z" fill="#8d7460" />
            </marker>
            <marker id="graph-arrow-hot" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto">
              <path d="M0,1 L8,4 L0,7 Z" fill="#c24e1d" />
            </marker>
          </defs>
          {graph.links.map((link, index) => {
            const a = pointOf(link.from);
            const b = pointOf(link.to);
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const dist = Math.hypot(dx, dy) || 1;
            const start = {
              x: a.x + (dx / dist) * 22,
              y: a.y + (dy / dist) * 22,
            };
            const end = {
              x: b.x - (dx / dist) * 22,
              y: b.y - (dy / dist) * 22,
            };
            const hot =
              !active ||
              link.from === active ||
              link.to === active ||
              (highlight.includes(link.from) && highlight.includes(link.to));
            return (
              <g key={`${link.from}-${link.to}-${index}`} opacity={hot ? 1 : 0.12}>
                <line
                  x1={start.x}
                  y1={start.y}
                  x2={end.x}
                  y2={end.y}
                  stroke={hot && active ? "#c24e1d" : "#8d7460"}
                  strokeWidth={hot && active ? 2 : 1.2}
                  markerEnd={hot && active ? "url(#graph-arrow-hot)" : "url(#graph-arrow)"}
                />
                {hot && (active || compact) && (
                  <text
                    x={(start.x + end.x) / 2}
                    y={(start.y + end.y) / 2 - 6}
                    textAnchor="middle"
                    className="fill-[var(--ink-soft)]"
                    fontSize={compact ? 9 : 10}
                  >
                    {link.label || link.type}
                  </text>
                )}
              </g>
            );
          })}
          {graph.nodes.map((node) => {
            const point = pointOf(node.name);
            const hot = !active || focusSet.has(node.name);
            const isSel = selected === node.name;
            const r = 8 + Math.min(6, (degree.get(node.name) || 0) * 1.4);
            return (
              <g
                key={node.name}
                transform={`translate(${point.x}, ${point.y})`}
                opacity={hot ? 1 : 0.18}
                onMouseEnter={() => setHover(node.name)}
                onMouseLeave={() => setHover(null)}
              >
                <circle
                  r={isSel ? r + 3 : r}
                  fill={kindColor(node.kind)}
                  stroke={isSel ? "#241c16" : "#fffaf1"}
                  strokeWidth={isSel ? 2.4 : 1.6}
                  className="cursor-pointer"
                  onPointerDown={(event) => onPointerDown(event, node.name)}
                  onClick={() => setSelected(node.name)}
                />
                <text
                  y={r + 13}
                  textAnchor="middle"
                  className="pointer-events-none fill-[var(--ink)]"
                  fontSize={compact ? 10 : 11}
                  fontWeight={isSel ? 600 : 500}
                >
                  {shortName(node.name)}
                </text>
              </g>
            );
          })}
        </svg>
        {!compact && (
          <p className="pointer-events-none absolute left-3 top-3 text-xs text-[var(--ink-soft)]">
            ลากโหนดได้ · กดโหนดเพื่อเน้นเส้นที่เชื่อม
          </p>
        )}
      </div>

      {!compact && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap gap-2">
            {kinds.map((kind) => (
              <span key={kind} className="inline-flex items-center gap-1 text-xs text-[var(--ink-soft)]">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: kindColor(kind) }} />
                {kindLabel(kind)}
              </span>
            ))}
          </div>
          {selectedNode ? (
            <div className="rounded-2xl border border-[var(--line)] bg-white px-4 py-3">
              <p className="font-semibold">{selectedNode.name}</p>
              {selectedNode.thai && (
                <p className="text-sm text-[var(--ink-soft)]">{selectedNode.thai}</p>
              )}
              {selectedNode.definition && (
                <p className="mt-1 text-sm leading-relaxed">{selectedNode.definition}</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-[var(--ink-soft)]">
              {graph.nodes.length} โหนด · {graph.links.length} ความสัมพันธ์
            </p>
          )}
        </div>
      )}
    </div>
  );
}
