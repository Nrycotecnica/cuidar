import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ajustar, paraMundo, zoomEm, type Pt, type Vista } from "../lib/geom";

export interface EventoMundo {
  p: Pt; // coordenada do mundo
  sx: number;
  sy: number;
  vista: Vista;
  shift: boolean;
}

interface Props {
  extensao: [number, number, number, number] | null;
  desenhar: (ctx: CanvasRenderingContext2D, v: Vista) => void;
  /** Retorne true para "capturar" o arrasto (ex.: mover nó) em vez de fazer pan. */
  aoPressionar?: (e: EventoMundo) => boolean | void;
  aoMover?: (e: EventoMundo, arrastando: boolean) => void;
  aoSoltar?: (e: EventoMundo) => void;
  aoClicar?: (e: EventoMundo) => void;
  cursor?: string;
  altura?: number | string;
  unidade?: string;
  sobreposicao?: ReactNode;
  idTeste?: string;
}

export default function CanvasView({ extensao, desenhar, aoPressionar, aoMover, aoSoltar, aoClicar, cursor = "default", altura = 560, unidade = "m", sobreposicao, idTeste }: Props) {
  const caixa = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [vista, setVista] = useState<Vista | null>(null);
  const vistaRef = useRef<Vista | null>(null);
  vistaRef.current = vista;
  const [coord, setCoord] = useState<Pt | null>(null);
  const arraste = useRef<{ sx: number; sy: number; tipo: "pan" | "captura"; vista0: Vista; moveu: boolean } | null>(null);
  const extRef = useRef(extensao);

  const enquadrar = useCallback(() => {
    const el = caixa.current;
    if (!el) return;
    setVista(ajustar(extRef.current, el.clientWidth, el.clientHeight));
  }, []);

  // Enquadramento inicial e quando a extensão mudar significativamente
  const chaveExt = extensao ? extensao.map((v) => v.toFixed(3)).join(",") : "";
  useEffect(() => {
    extRef.current = extensao;
    enquadrar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveExt]);

  // Redimensionamento
  useEffect(() => {
    const el = caixa.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setVista((v) => (v ? { ...v, w: el.clientWidth, h: el.clientHeight } : ajustar(extRef.current, el.clientWidth, el.clientHeight)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Desenho (a cada renderização)
  useEffect(() => {
    const c = canvas.current;
    if (!c || !vista) return;
    const dpr = window.devicePixelRatio || 1;
    if (c.width !== Math.round(vista.w * dpr) || c.height !== Math.round(vista.h * dpr)) {
      c.width = Math.round(vista.w * dpr);
      c.height = Math.round(vista.h * dpr);
    }
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, vista.w, vista.h);
    ctx.fillStyle = "#fbfcfd";
    ctx.fillRect(0, 0, vista.w, vista.h);
    desenhar(ctx, vista);
  });

  // Zoom com a roda (listener não passivo para poder impedir a rolagem da página)
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const roda = (ev: WheelEvent) => {
      ev.preventDefault();
      const r = c.getBoundingClientRect();
      const fator = Math.exp(-ev.deltaY * 0.0015);
      setVista((v) => (v ? zoomEm(v, ev.clientX - r.left, ev.clientY - r.top, fator) : v));
    };
    c.addEventListener("wheel", roda, { passive: false });
    return () => c.removeEventListener("wheel", roda);
  }, []);

  const evento = (ev: React.PointerEvent): EventoMundo | null => {
    const v = vistaRef.current;
    const c = canvas.current;
    if (!v || !c) return null;
    const r = c.getBoundingClientRect();
    const sx = ev.clientX - r.left;
    const sy = ev.clientY - r.top;
    return { p: paraMundo(v, sx, sy), sx, sy, vista: v, shift: ev.shiftKey };
  };

  return (
    <div className="canvas-caixa" ref={caixa} style={{ height: altura }} data-testid={idTeste}>
      <canvas
        ref={canvas}
        style={{ cursor: arraste.current?.tipo === "pan" && arraste.current.moveu ? "grabbing" : cursor, width: "100%", height: "100%", display: "block", touchAction: "none" }}
        onPointerDown={(ev) => {
          const e = evento(ev);
          if (!e || !vistaRef.current) return;
          (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
          const capt = ev.button === 0 && aoPressionar ? aoPressionar(e) : false;
          arraste.current = { sx: e.sx, sy: e.sy, tipo: capt ? "captura" : "pan", vista0: vistaRef.current, moveu: false };
        }}
        onPointerMove={(ev) => {
          const e = evento(ev);
          if (!e) return;
          setCoord(e.p);
          const a = arraste.current;
          if (a) {
            if (Math.hypot(e.sx - a.sx, e.sy - a.sy) > 3) a.moveu = true;
            if (a.tipo === "pan" && a.moveu) {
              const v0 = a.vista0;
              setVista({ ...v0, cx: v0.cx - (e.sx - a.sx) / v0.escala, cy: v0.cy + (e.sy - a.sy) / v0.escala });
            } else if (a.tipo === "captura") aoMover?.(e, true);
          } else aoMover?.(e, false);
        }}
        onPointerUp={(ev) => {
          const e = evento(ev);
          const a = arraste.current;
          arraste.current = null;
          if (!e || !a) return;
          if (a.tipo === "captura") aoSoltar?.(e);
          if (!a.moveu && ev.button === 0) aoClicar?.(e);
        }}
        onPointerLeave={() => setCoord(null)}
      />
      <div className="canvas-barra">
        <button className="btn btn-mini" onClick={enquadrar} title="Enquadrar tudo">Ajustar à tela</button>
        <button className="btn btn-mini" onClick={() => setVista((v) => (v ? zoomEm(v, v.w / 2, v.h / 2, 1.4) : v))}>+</button>
        <button className="btn btn-mini" onClick={() => setVista((v) => (v ? zoomEm(v, v.w / 2, v.h / 2, 1 / 1.4) : v))}>−</button>
        {coord && (
          <span className="coord">
            x {coord[0].toLocaleString("pt-BR", { maximumFractionDigits: 2 })} · y {coord[1].toLocaleString("pt-BR", { maximumFractionDigits: 2 })} {unidade}
          </span>
        )}
      </div>
      {sobreposicao}
    </div>
  );
}

/** Utilitários de desenho em coordenadas do mundo. */
export function caminho(ctx: CanvasRenderingContext2D, v: Vista, pts: Pt[], fechado = false) {
  if (pts.length < 2) return;
  ctx.beginPath();
  pts.forEach(([x, y], i) => {
    const sx = (x - v.cx) * v.escala + v.w / 2;
    const sy = v.h / 2 - (y - v.cy) * v.escala;
    if (i === 0) ctx.moveTo(sx, sy);
    else ctx.lineTo(sx, sy);
  });
  if (fechado) ctx.closePath();
}

export function escalaGrafica(ctx: CanvasRenderingContext2D, v: Vista, unidadesPorMetro: number | null) {
  if (!unidadesPorMetro) return;
  const pxPorMetro = v.escala * unidadesPorMetro;
  const alvo = 120 / pxPorMetro;
  const passos = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500];
  const m = passos.find((p) => p >= alvo) || 500;
  const L = m * pxPorMetro;
  const x = v.w - L - 20;
  const y = v.h - 40;
  ctx.strokeStyle = "#222";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + L, y);
  ctx.moveTo(x, y - 5);
  ctx.lineTo(x, y + 5);
  ctx.moveTo(x + L, y - 5);
  ctx.lineTo(x + L, y + 5);
  ctx.stroke();
  ctx.fillStyle = "#222";
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(`${m.toLocaleString("pt-BR")} m`, x + L / 2, y - 7);
}
