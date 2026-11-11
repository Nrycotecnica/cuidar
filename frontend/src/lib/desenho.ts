import type { Vista, Pt } from "./geom";

// Cores ACI básicas adaptadas a fundo claro
const ACI: Record<number, string> = { 1: "#d32f2f", 2: "#b8860b", 3: "#2e7d32", 4: "#00838f", 5: "#1565c0", 6: "#8e24aa", 7: "#222", 8: "#808080", 9: "#a8a8a8" };
export const corAci = (c: number | undefined) => (c !== undefined && ACI[Math.abs(c)]) || "#555";

function T(v: Vista, x: number, y: number): Pt {
  return [(x - v.cx) * v.escala + v.w / 2, v.h / 2 - (y - v.cy) * v.escala];
}

/** Desenha entidades normalizadas (formato do backend) em unidades do desenho. */
export function desenharEntidades(ctx: CanvasRenderingContext2D, v: Vista, ents: any[], camadas: any[], ocultas: Set<number>) {
  ctx.lineWidth = 1;
  let corAtual = "";
  for (const e of ents) {
    if (ocultas.has(e.l)) continue;
    const cor = corAci(camadas[e.l]?.cor);
    if (cor !== corAtual) {
      ctx.strokeStyle = cor;
      ctx.fillStyle = cor;
      corAtual = cor;
    }
    if (e.t === "L") {
      const a = T(v, e.p[0], e.p[1]);
      const b = T(v, e.p[2], e.p[3]);
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
    } else if (e.t === "P") {
      const p = e.p as number[];
      ctx.beginPath();
      for (let i = 0; i < p.length; i += 2) {
        const s = T(v, p[i], p[i + 1]);
        if (i === 0) ctx.moveTo(s[0], s[1]);
        else ctx.lineTo(s[0], s[1]);
      }
      if (e.c) ctx.closePath();
      ctx.stroke();
    } else if (e.t === "C" || e.t === "A") {
      const c = T(v, e.c[0], e.c[1]);
      const r = e.r * v.escala;
      if (r < 0.3) continue;
      ctx.beginPath();
      if (e.t === "C") ctx.arc(c[0], c[1], r, 0, Math.PI * 2);
      else ctx.arc(c[0], c[1], r, (-e.a0 * Math.PI) / 180, (-e.a1 * Math.PI) / 180, true);
      ctx.stroke();
    } else if (e.t === "T") {
      const px = (e.h || 1) * v.escala;
      if (px < 4 || px > 400 || !e.s) continue;
      const s = T(v, e.p[0], e.p[1]);
      ctx.save();
      ctx.translate(s[0], s[1]);
      if (e.r) ctx.rotate((-e.r * Math.PI) / 180);
      ctx.font = `${px.toFixed(1)}px system-ui, sans-serif`;
      ctx.textAlign = "left";
      ctx.fillText(String(e.s).slice(0, 200), 0, 0);
      ctx.restore();
    }
  }
}

export function poligono(ctx: CanvasRenderingContext2D, v: Vista, pts: number[][], fill: string | null, stroke: string, largura = 1.5, tracejado?: number[]) {
  if (!pts || pts.length < 2) return;
  ctx.beginPath();
  pts.forEach((p, i) => {
    const s = T(v, p[0], p[1]);
    if (i === 0) ctx.moveTo(s[0], s[1]);
    else ctx.lineTo(s[0], s[1]);
  });
  ctx.closePath();
  if (fill) {
    ctx.fillStyle = fill;
    ctx.fill();
  }
  ctx.setLineDash(tracejado || []);
  ctx.strokeStyle = stroke;
  ctx.lineWidth = largura;
  ctx.stroke();
  ctx.setLineDash([]);
}

export function marcaPonto(ctx: CanvasRenderingContext2D, v: Vista, p: Pt, cor = "#c00") {
  const s = T(v, p[0], p[1]);
  ctx.strokeStyle = cor;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(s[0] - 7, s[1]);
  ctx.lineTo(s[0] + 7, s[1]);
  ctx.moveTo(s[0], s[1] - 7);
  ctx.lineTo(s[0], s[1] + 7);
  ctx.stroke();
}

export function linhaCota(ctx: CanvasRenderingContext2D, v: Vista, a: Pt, b: Pt, texto: string, cor = "#c00") {
  const sa = T(v, a[0], a[1]);
  const sb = T(v, b[0], b[1]);
  ctx.strokeStyle = cor;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(sa[0], sa[1]);
  ctx.lineTo(sb[0], sb[1]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.font = "bold 13px system-ui, sans-serif";
  const mx = (sa[0] + sb[0]) / 2;
  const my = (sa[1] + sb[1]) / 2;
  const w = ctx.measureText(texto).width;
  ctx.fillStyle = "rgba(255,255,255,.92)";
  ctx.fillRect(mx - w / 2 - 4, my - 18, w + 8, 18);
  ctx.fillStyle = cor;
  ctx.textAlign = "center";
  ctx.fillText(texto, mx, my - 4);
}
