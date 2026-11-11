// Gráfico SVG simples de curvas (vazão × pressão)
import { fmt } from "../lib/format";

export interface Serie {
  nome: string;
  pontos: [number, number][];
  cor: string;
  tracejado?: boolean;
}

export default function Grafico({ series, marcador, rotuloX = "Vazão (m³/h)", rotuloY = "Pressão (Pa)", altura = 300 }: {
  series: Serie[]; marcador?: { x: number; y: number; rotulo: string } | null; rotuloX?: string; rotuloY?: string; altura?: number;
}) {
  const W = 640, H = altura, ml = 62, mr = 16, mt = 16, mb = 44;
  const todos = series.flatMap((s) => s.pontos).concat(marcador ? [[marcador.x, marcador.y] as [number, number]] : []);
  if (!todos.length) return <div className="vazio">Sem dados para o gráfico.</div>;
  const xmax = niceMax(Math.max(...todos.map((p) => p[0])));
  const ymax = niceMax(Math.max(...todos.map((p) => p[1])) * 1.05);
  const X = (x: number) => ml + (x / xmax) * (W - ml - mr);
  const Y = (y: number) => H - mb - (y / ymax) * (H - mt - mb);
  const ticks = (max: number) => Array.from({ length: 6 }, (_, i) => (max * i) / 5);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="grafico" role="img" aria-label="Gráfico de curvas">
      {ticks(ymax).map((t) => (
        <g key={"y" + t}>
          <line x1={ml} x2={W - mr} y1={Y(t)} y2={Y(t)} stroke="#e3e7ec" />
          <text x={ml - 6} y={Y(t) + 4} textAnchor="end" fontSize="11" fill="#555">{fmt(t)}</text>
        </g>
      ))}
      {ticks(xmax).map((t) => (
        <g key={"x" + t}>
          <line x1={X(t)} x2={X(t)} y1={mt} y2={H - mb} stroke="#eef1f4" />
          <text x={X(t)} y={H - mb + 16} textAnchor="middle" fontSize="11" fill="#555">{fmt(t)}</text>
        </g>
      ))}
      <line x1={ml} x2={W - mr} y1={H - mb} y2={H - mb} stroke="#333" />
      <line x1={ml} x2={ml} y1={mt} y2={H - mb} stroke="#333" />
      <text x={(ml + W - mr) / 2} y={H - 8} textAnchor="middle" fontSize="12" fill="#333">{rotuloX}</text>
      <text x={14} y={(mt + H - mb) / 2} textAnchor="middle" fontSize="12" fill="#333" transform={`rotate(-90 14 ${(mt + H - mb) / 2})`}>{rotuloY}</text>
      {series.map((s) => (
        <polyline key={s.nome} fill="none" stroke={s.cor} strokeWidth={2.2} strokeDasharray={s.tracejado ? "6 4" : undefined}
          points={s.pontos.filter((p) => p[1] <= ymax * 1.2).map((p) => `${X(p[0])},${Y(Math.min(p[1], ymax))}`).join(" ")} />
      ))}
      {marcador && (
        <g>
          <circle cx={X(marcador.x)} cy={Y(marcador.y)} r={5} fill="#111" />
          <text x={X(marcador.x) + 8} y={Y(marcador.y) - 8} fontSize="11" fill="#111">{marcador.rotulo}</text>
        </g>
      )}
      <g transform={`translate(${W - mr - 210}, ${mt + 6})`}>
        {series.map((s, i) => (
          <g key={s.nome} transform={`translate(0, ${i * 16})`}>
            <line x1={0} x2={22} y1={0} y2={0} stroke={s.cor} strokeWidth={2.5} strokeDasharray={s.tracejado ? "6 4" : undefined} />
            <text x={28} y={4} fontSize="11" fill="#333">{s.nome}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}

function niceMax(v: number): number {
  if (!(v > 0)) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
