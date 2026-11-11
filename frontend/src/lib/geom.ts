// Transformação de visualização 2D (mundo com y para cima ↔ tela com y para baixo).
export type Pt = [number, number];
export interface Vista {
  cx: number; // centro em coordenadas do mundo
  cy: number;
  escala: number; // pixels por unidade do mundo
  w: number; // tamanho do canvas em px
  h: number;
}

export function paraTela(v: Vista, x: number, y: number): Pt {
  return [(x - v.cx) * v.escala + v.w / 2, v.h / 2 - (y - v.cy) * v.escala];
}

export function paraMundo(v: Vista, sx: number, sy: number): Pt {
  return [(sx - v.w / 2) / v.escala + v.cx, (v.h / 2 - sy) / v.escala + v.cy];
}

/** Zoom mantendo fixo o ponto do mundo sob o cursor (sx, sy). */
export function zoomEm(v: Vista, sx: number, sy: number, fator: number): Vista {
  const [wx, wy] = paraMundo(v, sx, sy);
  const escala = Math.min(Math.max(v.escala * fator, 1e-9), 1e9);
  const cx = wx - (sx - v.w / 2) / escala;
  const cy = wy - (v.h / 2 - sy) / escala;
  return { ...v, escala, cx, cy };
}

export function ajustar(ext: [number, number, number, number] | null | undefined, w: number, h: number, margem = 0.06): Vista {
  if (!ext || !(ext[2] > ext[0]) || !(ext[3] > ext[1])) return { cx: 0, cy: 0, escala: 20, w, h };
  const [x0, y0, x1, y1] = ext;
  const ew = (x1 - x0) * (1 + 2 * margem);
  const eh = (y1 - y0) * (1 + 2 * margem);
  const escala = Math.min(w / ew, h / eh);
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, escala, w, h };
}

export function dist(a: Pt, b: Pt): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

export function distPontoSegmento(p: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy;
  if (l2 === 0) return dist(p, a);
  let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2;
  t = Math.max(0, Math.min(1, t));
  return dist(p, [a[0] + t * dx, a[1] + t * dy]);
}

export function pontoEmPoligono(p: Pt, poly: Pt[]): boolean {
  let dentro = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) dentro = !dentro;
  }
  return dentro;
}

export function retangulo(a: Pt, b: Pt): Pt[] {
  const x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]);
  const y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
  return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
}

export function extensaoPontos(pts: Pt[]): [number, number, number, number] | null {
  if (!pts.length) return null;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) {
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
  }
  if (x1 - x0 < 1e-9) { x0 -= 1; x1 += 1; }
  if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1; }
  return [x0, y0, x1, y1];
}

/** Arredonda a um passo de grade (para posicionar nós). */
export function encaixar(v: number, passo: number): number {
  return passo > 0 ? Math.round(v / passo) * passo : v;
}
