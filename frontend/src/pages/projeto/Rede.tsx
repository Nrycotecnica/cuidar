import { useEffect, useMemo, useRef, useState } from "react";
import CanvasView, { escalaGrafica } from "../../components/CanvasView";
import { Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { poligono, marcaPonto } from "../../lib/desenho";
import { ENTRADAS_CAPTOR, fmt, numero, TIPOS_CAPTOR } from "../../lib/format";
import { dist, distPontoSegmento, encaixar, extensaoPontos, retangulo, type Pt, type Vista } from "../../lib/geom";
import type { CtxProjeto } from "./Projeto";

type Tipo = "captor" | "juncao" | "ponto" | "filtro" | "exaustor" | "descarga";
type Ferr = "selecionar" | Tipo | "ligar" | "excluir" | "bloqueio";

const NOMES: Record<Tipo, string> = { captor: "Captor", juncao: "Junção", ponto: "Ponto/curva", filtro: "Filtro", exaustor: "Exaustor", descarga: "Descarga" };
const PREFIXO: Record<Tipo, string> = { captor: "C", juncao: "J", ponto: "P", filtro: "F", exaustor: "E", descarga: "D" };
const COR: Record<string, string> = { captor: "#2e7d32", juncao: "#222", ponto: "#777", filtro: "#6a1b9a", exaustor: "#1565c0", descarga: "#555" };

function T(v: Vista, x: number, y: number): Pt {
  return [(x - v.cx) * v.escala + v.w / 2, v.h / 2 - (y - v.cy) * v.escala];
}

function novoId(prefixo: string, existentes: Set<string>) {
  let i = 1;
  while (existentes.has(`${prefixo}${i}`)) i++;
  return `${prefixo}${i}`;
}

export default function Rede({ ctx }: { ctx: CtxProjeto }) {
  const { projeto: p } = ctx;
  const { pode } = useAuth();
  const editavel = pode("projetos.editar") && !["aprovado", "liberado_fabricacao"].includes(p.status);
  const [rede, setRede] = useState<any>(null);
  const [nodes, setNodes] = useState<any[]>([]);
  const [segs, setSegs] = useState<any[]>([]);
  const [sujo, setSujo] = useState(false);
  const [ferr, setFerr] = useState<Ferr>("selecionar");
  const [sel, setSel] = useState<{ tipo: "no" | "trecho"; id: string } | null>(null);
  const [ligarDe, setLigarDe] = useState<string | null>(null);
  const [bloqIni, setBloqIni] = useState<Pt | null>(null);
  const [mouse, setMouse] = useState<Pt | null>(null);
  const [grade, setGrade] = useState("0,1");
  const [estrategia, setEstrategia] = useState("menor_perda");
  const [calc, setCalc] = useState<any>(null);
  const [alts, setAlts] = useState<any[] | null>(null);
  const [erro, setErro] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [ambiente, setAmbiente] = useState<any>(p.ambiente || {});
  const arrasto = useRef<{ id: string; vertice?: number } | null>(null);

  const carregar = async () => {
    const r = await api.get(`/projetos/${p.id}/rede`);
    setRede(r);
    setNodes(r.dados?.nodes || []);
    setSegs(r.dados?.segments || []);
    setSujo(false);
  };
  useEffect(() => {
    carregar().catch(setErro);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.id]);
  useEffect(() => setAmbiente(p.ambiente || {}), [p.ambiente]);
  useEffect(() => {
    if (ctx.calcId) api.get(`/calculos/${ctx.calcId}`).then(setCalc).catch(() => setCalc(null));
    else setCalc(null);
  }, [ctx.calcId]);

  const nos = useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), [nodes]);
  const res = calc?.resultados;
  const trechosRes = useMemo(() => Object.fromEntries(((res?.trechos as any[]) || []).map((t) => [t.id, t])), [res]);
  const resAtual = calc && rede && calc.tipo === "rede" && calc.rede_versao === rede.versao && !sujo;

  const extensao = useMemo(() => {
    const pts: Pt[] = nodes.map((n) => [n.x, n.y] as Pt);
    for (const q of ambiente.contorno || []) pts.push(q);
    for (const s of segs) for (const q of s.path || []) pts.push(q);
    return extensaoPontos(pts) || [0, 0, 20, 12];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rede, ambiente.contorno]);

  const pontosTrecho = (s: any): Pt[] => {
    const a = nos[s.from], b = nos[s.to];
    if (!a || !b) return [];
    return [[a.x, a.y], ...(s.path || []), [b.x, b.y]];
  };

  const passo = numero(grade) || 0;
  const alterar = (n: any[], s: any[]) => { setNodes(n); setSegs(s); setSujo(true); setMsg(null); };

  const acharNo = (pt: Pt, v: Vista) => {
    const tol = 10 / v.escala;
    let melhor: any = null, dm = Infinity;
    for (const n of nodes) {
      const d = dist(pt, [n.x, n.y]);
      if (d < tol && d < dm) { melhor = n; dm = d; }
    }
    return melhor;
  };
  const acharTrecho = (pt: Pt, v: Vista) => {
    const tol = 8 / v.escala;
    for (const s of segs) {
      const ps = pontosTrecho(s);
      for (let i = 1; i < ps.length; i++) if (distPontoSegmento(pt, ps[i - 1], ps[i]) < tol) return s;
    }
    return null;
  };

  const desenhar = (c: CanvasRenderingContext2D, v: Vista) => {
    // grade de 1 m quando o zoom permitir
    if (v.escala > 12) {
      c.strokeStyle = "#eef1f4";
      c.lineWidth = 1;
      const [x0, y1] = [v.cx - v.w / 2 / v.escala, v.cy + v.h / 2 / v.escala];
      const [x1, y0] = [v.cx + v.w / 2 / v.escala, v.cy - v.h / 2 / v.escala];
      c.beginPath();
      for (let x = Math.floor(x0); x <= x1; x++) { const s = T(v, x, 0)[0]; c.moveTo(s, 0); c.lineTo(s, v.h); }
      for (let y = Math.floor(y0); y <= y1; y++) { const s = T(v, 0, y)[1]; c.moveTo(0, s); c.lineTo(v.w, s); }
      c.stroke();
    }
    if (ambiente.contorno) poligono(c, v, ambiente.contorno, "rgba(255,255,255,1)", "#555", 2);
    for (const q of ambiente.pilares || []) poligono(c, v, q.pontos, "#777", "#333", 1);
    for (const q of ambiente.obstaculos || []) {
      poligono(c, v, q.pontos, "rgba(255,152,0,.18)", "#e65100", 1.2);
      if (q.nome) {
        const xs = q.pontos.map((z: number[]) => z[0]), ys = q.pontos.map((z: number[]) => z[1]);
        const s = T(v, (Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2);
        c.fillStyle = "#a04000"; c.font = "11px system-ui"; c.textAlign = "center"; c.fillText(q.nome, s[0], s[1]);
      }
    }
    for (const q of ambiente.bloqueios || []) poligono(c, v, q.pontos, "rgba(198,40,40,.12)", "#c62828", 1.2, [6, 4]);
    if (bloqIni && mouse) poligono(c, v, retangulo(bloqIni, mouse), "rgba(198,40,40,.12)", "#c62828", 1.2, [6, 4]);

    // trechos
    for (const s of segs) {
      const ps = pontosTrecho(s);
      if (ps.length < 2) continue;
      const t = resAtual ? trechosRes[s.id] : null;
      const d = ((t?.diametro_mm || s.diametro_mm || t?.largura_mm || s.largura_mm || 0) as number) / 1000;
      const descarga = t?.lado === "descarga" || nos[s.from]?.type === "exaustor";
      c.lineCap = "round";
      c.lineJoin = "round";
      c.strokeStyle = sel?.tipo === "trecho" && sel.id === s.id ? "#1e88e5" : descarga ? "#78909c" : s.travado ? "#8d6e63" : "#c62828";
      c.lineWidth = Math.max(d * v.escala, 3);
      c.beginPath();
      ps.forEach((q, i) => { const z = T(v, q[0], q[1]); if (i) c.lineTo(z[0], z[1]); else c.moveTo(z[0], z[1]); });
      c.stroke();
      // seta de sentido no maior segmento
      let im = 1, lm = 0;
      for (let i = 1; i < ps.length; i++) { const l = dist(ps[i - 1], ps[i]); if (l > lm) { lm = l; im = i; } }
      const a = T(v, ps[im - 1][0], ps[im - 1][1]), b = T(v, ps[im][0], ps[im][1]);
      const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
      const m: Pt = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      c.fillStyle = "#fff";
      c.beginPath();
      c.moveTo(m[0] + 7 * Math.cos(ang), m[1] + 7 * Math.sin(ang));
      c.lineTo(m[0] + 6 * Math.cos(ang + 2.4), m[1] + 6 * Math.sin(ang + 2.4));
      c.lineTo(m[0] + 6 * Math.cos(ang - 2.4), m[1] + 6 * Math.sin(ang - 2.4));
      c.fill();
      // rótulo
      if (v.escala > 6) {
        let txt = s.label || s.id;
        if (t) txt += ` Ø${fmt(t.diametro_mm)} · ${fmt(t.vazao_m3h)} m³/h · ${fmt(t.velocidade_ms, 1)} m/s`;
        else if (s.diametro_mm) txt += ` Ø${fmt(s.diametro_mm)}`;
        c.save();
        c.translate(m[0], m[1]);
        let r = ang;
        if (r > Math.PI / 2 || r < -Math.PI / 2) r += Math.PI;
        c.rotate(r);
        c.font = "11px system-ui";
        c.textAlign = "center";
        const w = c.measureText(txt).width;
        c.fillStyle = "rgba(255,255,255,.85)";
        c.fillRect(-w / 2 - 3, -Math.max(d * v.escala, 3) / 2 - 17, w + 6, 14);
        c.fillStyle = "#333";
        c.fillText(txt, 0, -Math.max(d * v.escala, 3) / 2 - 6);
        c.restore();
      }
      if (sel?.tipo === "trecho" && sel.id === s.id) (s.path || []).forEach((q: Pt) => marcaPonto(c, v, q, "#1e88e5"));
    }
    if (ligarDe && mouse && nos[ligarDe]) {
      const a = T(v, nos[ligarDe].x, nos[ligarDe].y), b = T(v, mouse[0], mouse[1]);
      c.setLineDash([6, 4]); c.strokeStyle = "#1e88e5"; c.lineWidth = 2;
      c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); c.setLineDash([]);
    }
    // nós
    for (const n of nodes) {
      const s = T(v, n.x, n.y);
      const selec = sel?.tipo === "no" && sel.id === n.id;
      c.fillStyle = COR[n.type] || "#000";
      c.strokeStyle = selec ? "#1e88e5" : "#fff";
      c.lineWidth = selec ? 3 : 1.5;
      c.beginPath();
      if (n.type === "captor") c.rect(s[0] - 7, s[1] - 7, 14, 14);
      else if (n.type === "filtro") c.rect(s[0] - 10, s[1] - 8, 20, 16);
      else if (n.type === "exaustor") c.arc(s[0], s[1], 10, 0, Math.PI * 2);
      else if (n.type === "descarga") c.arc(s[0], s[1], 7, 0, Math.PI * 2);
      else c.arc(s[0], s[1], n.type === "juncao" ? 4.5 : 3.5, 0, Math.PI * 2);
      c.fill();
      c.stroke();
      if (n.type !== "juncao" && n.type !== "ponto") {
        c.font = "bold 12px system-ui";
        c.textAlign = "left";
        c.fillStyle = "#1d2733";
        let txt = n.label || n.id;
        const cr = resAtual && n.type === "captor" ? res.captores?.find((x: any) => x.id === n.id) : null;
        if (cr) txt += ` (${fmt(cr.vazao_m3h)} m³/h)`;
        c.fillText(txt, s[0] + 12, s[1] - 9);
      }
    }
    // sugestão de renovação
    const sug = res?.sugestao_posicionamento;
    if (sug && calc?.tipo === "renovacao") {
      for (const q of sug.exaustores) { const s = T(v, q[0], q[1]); c.fillStyle = "#1565c0"; c.beginPath(); c.arc(s[0], s[1], 9, 0, 7); c.fill(); }
      for (const q of sug.entradas) { const s = T(v, q[0], q[1]); c.fillStyle = "#2e7d32"; c.fillRect(s[0] - 12, s[1] - 5, 24, 10); }
    }
    escalaGrafica(c, v, 1);
  };

  const aoPressionar = ({ p: pt, vista }: { p: Pt; vista: Vista }) => {
    if (!editavel || ferr !== "selecionar") return false;
    if (sel?.tipo === "trecho") {
      const s = segs.find((x) => x.id === sel.id);
      const idx = (s?.path || []).findIndex((q: Pt) => dist(q, pt) < 8 / vista.escala);
      if (s && idx >= 0) { arrasto.current = { id: s.id, vertice: idx }; return true; }
    }
    const n = acharNo(pt, vista);
    if (n) { setSel({ tipo: "no", id: n.id }); arrasto.current = { id: n.id }; return true; }
    return false;
  };
  const aoMover = ({ p: pt }: { p: Pt }, arrastando: boolean) => {
    setMouse(pt);
    const a = arrasto.current;
    if (!arrastando || !a) return;
    const q: Pt = [encaixar(pt[0], passo), encaixar(pt[1], passo)];
    if (a.vertice !== undefined) {
      setSegs(segs.map((s) => (s.id === a.id ? { ...s, path: s.path.map((z: Pt, i: number) => (i === a.vertice ? q : z)) } : s)));
    } else setNodes(nodes.map((n) => (n.id === a.id ? { ...n, x: +q[0].toFixed(3), y: +q[1].toFixed(3) } : n)));
    setSujo(true);
  };

  const aoClicar = ({ p: pt, vista }: { p: Pt; vista: Vista }) => {
    setErro(null);
    const q: Pt = [+encaixar(pt[0], passo).toFixed(3), +encaixar(pt[1], passo).toFixed(3)];
    if (ferr === "selecionar") {
      const n = acharNo(pt, vista);
      if (n) return setSel({ tipo: "no", id: n.id });
      const s = acharTrecho(pt, vista);
      setSel(s ? { tipo: "trecho", id: s.id } : null);
      return;
    }
    if (!editavel) return;
    if (ferr in NOMES) {
      const tipo = ferr as Tipo;
      if (tipo === "exaustor" && nodes.some((n) => n.type === "exaustor")) { setErro("A rede deve ter apenas um exaustor."); return; }
      const id = novoId(PREFIXO[tipo], new Set(nodes.map((n) => n.id)));
      const n: any = { id, type: tipo, x: q[0], y: q[1], label: id };
      if (tipo === "captor") n.captor = { tipo: "vazao_informada", entrada: "flangeada" };
      if (tipo === "filtro") n.filtro_tipo = "mangas";
      alterar([...nodes, n], segs);
      setSel({ tipo: "no", id });
    } else if (ferr === "ligar") {
      const n = acharNo(pt, vista);
      if (!n) return;
      if (!ligarDe) setLigarDe(n.id);
      else if (n.id !== ligarDe) {
        if (segs.some((s) => s.from === ligarDe)) { setErro("O nó de origem já possui um trecho de saída (a rede é uma árvore no sentido do escoamento)."); setLigarDe(null); return; }
        const id = novoId("S", new Set(segs.map((s) => s.id)));
        alterar(nodes, [...segs, { id, from: ligarDe, to: n.id, label: id }]);
        setSel({ tipo: "trecho", id });
        setLigarDe(null);
      }
    } else if (ferr === "excluir") {
      const n = acharNo(pt, vista);
      if (n) { alterar(nodes.filter((x) => x.id !== n.id), segs.filter((s) => s.from !== n.id && s.to !== n.id)); setSel(null); return; }
      const s = acharTrecho(pt, vista);
      if (s) { alterar(nodes, segs.filter((x) => x.id !== s.id)); setSel(null); return; }
      const bl = (ambiente.bloqueios || []).findIndex((b: any) => {
        const xs = b.pontos.map((z: number[]) => z[0]), ys = b.pontos.map((z: number[]) => z[1]);
        return pt[0] >= Math.min(...xs) && pt[0] <= Math.max(...xs) && pt[1] >= Math.min(...ys) && pt[1] <= Math.max(...ys);
      });
      if (bl >= 0) salvarAmbiente({ ...ambiente, bloqueios: ambiente.bloqueios.filter((_: any, i: number) => i !== bl) });
    } else if (ferr === "bloqueio") {
      if (!bloqIni) setBloqIni(q);
      else {
        salvarAmbiente({ ...ambiente, bloqueios: [...(ambiente.bloqueios || []), { pontos: retangulo(bloqIni, q) }] });
        setBloqIni(null);
      }
    }
  };

  const salvarAmbiente = async (amb: any) => {
    try {
      await api.put(`/projetos/${p.id}`, { ambiente: amb });
      setAmbiente(amb);
      await ctx.recarregar();
    } catch (e) { setErro(e); }
  };

  const salvar = async () => {
    const r = await api.put(`/projetos/${p.id}/rede`, { dados: { nodes, segments: segs } });
    setRede(r);
    setSujo(false);
    return r;
  };

  const calcular = async (exaustor_id?: number) => {
    setErro(null);
    try {
      if (sujo) await salvar();
      const c = await api.post(`/projetos/${p.id}/calcular`, { estrategia, exaustor_id });
      await carregar();
      await ctx.recarregarCalculos();
      ctx.setCalcId(c.id);
      setCalc(c);
      const r = c.resultados;
      setMsg(c.tipo === "rede"
        ? `Cálculo nº ${c.id}: ${fmt(r.vazao_total_m3h)} m³/h, pressão total ${fmt(r.pressao_total_ventilador_pa)} Pa — ${r.selecao_exaustor?.selecionado ? "exaustor " + r.selecao_exaustor.selecionado.nome : "nenhum exaustor compatível"}${r.bloqueios.length ? ` — ${r.bloqueios.length} bloqueio(s)` : ""}.`
        : `Cálculo nº ${c.id}: exaustão ${fmt(r.vazao_exaustao_m3h)} m³/h.`);
    } catch (e) { setErro(e); }
  };

  if (!rede) return <Carregando />;
  const noSel = sel?.tipo === "no" ? nodes.find((n) => n.id === sel.id) : null;
  const trSel = sel?.tipo === "trecho" ? segs.find((s) => s.id === sel.id) : null;
  const updNo = (patch: any) => alterar(nodes.map((n) => (n.id === noSel.id ? { ...n, ...patch } : n)), segs);
  const updCap = (patch: any) => updNo({ captor: { ...(noSel.captor || {}), ...patch } });
  const updTr = (patch: any) => alterar(nodes, segs.map((s) => (s.id === trSel.id ? { ...s, ...patch } : s)));
  const numIn = (val: any, set: (n: number | null) => void, ph?: string) => (
    <input inputMode="decimal" defaultValue={val ?? ""} key={`${sel?.id}-${ph}-${val}`} placeholder={ph} disabled={!editavel} onBlur={(e) => set(numero(e.target.value))} />
  );
  const ferramentas: [Ferr, string][] = [["selecionar", "Selecionar/mover"], ["captor", "+ Captor"], ["juncao", "+ Junção"], ["ponto", "+ Ponto/curva"], ["filtro", "+ Filtro"], ["exaustor", "+ Exaustor"], ["descarga", "+ Descarga"], ["ligar", "Ligar nós"], ["excluir", "Excluir"], ["bloqueio", "Área bloqueada"]];

  return (
    <div className="lado-a-lado">
      <div>
        <div className="ferramentas">
          {ferramentas.filter(([f]) => editavel || f === "selecionar").map(([f, r]) => (
            <button key={f} className={ferr === f ? "btn btn-mini ativo" : "btn btn-mini"} onClick={() => { setFerr(f); setLigarDe(null); setBloqIni(null); }}>{r}</button>
          ))}
          <span className="sep" />
          <label className="nota">Grade (m) <input style={{ width: 60 }} value={grade} onChange={(e) => setGrade(e.target.value)} /></label>
        </div>
        <CanvasView idTeste="editor-rede" extensao={extensao as any} desenhar={desenhar} aoPressionar={aoPressionar} aoMover={aoMover} aoSoltar={() => { arrasto.current = null; }} aoClicar={aoClicar}
          cursor={ferr === "selecionar" ? "default" : "crosshair"} altura={600} />
        <div className="legenda-rede">
          <span style={{ ["--c" as any]: "#2e7d32" }}>Captor</span><span style={{ ["--c" as any]: "#6a1b9a" }}>Filtro</span>
          <span style={{ ["--c" as any]: "#1565c0" }}>Exaustor</span><span style={{ ["--c" as any]: "#c62828" }}>Duto de sucção</span>
          <span style={{ ["--c" as any]: "#78909c" }}>Descarga</span><span style={{ ["--c" as any]: "#8d6e63" }}>Trecho travado</span>
          <span style={{ ["--c" as any]: "rgba(198,40,40,.4)" }}>Área bloqueada</span><span style={{ ["--c" as any]: "#e65100" }}>Obstáculo</span>
        </div>
        <p className="nota">
          {ferr === "ligar" && (ligarDe ? `Origem: ${ligarDe}. Clique no nó de destino (sentido do escoamento).` : "Clique no nó de origem (ex.: captor) e depois no destino (rumo ao exaustor).")}
          {ferr === "bloqueio" && "Clique em dois cantos opostos para criar uma área onde dutos não podem passar."}
          {ferr === "selecionar" && "Clique para selecionar; arraste nós (ou vértices do trecho selecionado) para mover. Roda: zoom; arrastar o fundo: mover vista."}
        </p>
      </div>
      <div className="pilha">
        <Cartao titulo="Ações">
          <div className="acoes">
            {editavel && <BotaoAcao className="btn" disabled={!sujo} onClick={async () => { try { await salvar(); setMsg("Rede salva."); } catch (e) { setErro(e); } }}>Salvar rede</BotaoAcao>}
            {editavel && p.modulo !== "renovacao" && (
              <BotaoAcao className="btn" title="Refaz os trechos de sucção desviando de pilares, obstáculos e áreas bloqueadas" onClick={async () => {
                setErro(null);
                try {
                  if (sujo) await salvar();
                  const r = await api.post(`/projetos/${p.id}/rede/rotear`, {});
                  await carregar();
                  setMsg(`Roteamento concluído: ${fmt(r.comprimento_total_m, 1)} m de dutos de sucção. ${(r.avisos || []).join(" ")}`);
                } catch (e) { setErro(e); }
              }}>Rotear automaticamente</BotaoAcao>
            )}
          </div>
          {pode("calculos.executar") && (
            <div className="form-linha" style={{ marginTop: 8 }}>
              {p.modulo !== "renovacao" && (
                <Campo rotulo="Critério de dimensionamento">
                  <select value={estrategia} onChange={(e) => setEstrategia(e.target.value)}>
                    <option value="menor_perda">Menor perda de carga</option>
                    <option value="intermediaria">Intermediário</option>
                    <option value="economica">Menor diâmetro (menos material)</option>
                  </select>
                </Campo>
              )}
              <BotaoAcao className="btn btn-primario" onClick={() => calcular()}>Calcular</BotaoAcao>
              {p.modulo !== "renovacao" && (
                <BotaoAcao className="btn" onClick={async () => {
                  setErro(null);
                  try { if (sujo) await salvar(); setAlts((await api.post(`/projetos/${p.id}/alternativas`, {})).alternativas); } catch (e) { setErro(e); }
                }}>Gerar alternativas</BotaoAcao>
              )}
            </div>
          )}
          {sujo && <Alerta tipo="aviso">Alterações não salvas.</Alerta>}
          {calc && !resAtual && calc.tipo === "rede" && <p className="nota">Rótulos de cálculo ocultos: a rede mudou desde o cálculo nº {calc.id}. Recalcule.</p>}
          {resAtual && <p className="nota">Mostrando resultados do cálculo nº {calc.id}.</p>}
          <ErroBox erro={erro} />
          {msg && <Alerta tipo="ok">{msg}</Alerta>}
        </Cartao>

        {noSel && (
          <Cartao titulo={`${NOMES[noSel.type as Tipo] || noSel.type} ${noSel.id}`}>
            <div className="grade g2">
              <Campo rotulo="Rótulo"><input value={noSel.label || ""} disabled={!editavel} onChange={(e) => updNo({ label: e.target.value })} /></Campo>
              <div />
              <Campo rotulo="X (m)">{numIn(noSel.x, (v) => v !== null && updNo({ x: v }), "x")}</Campo>
              <Campo rotulo="Y (m)">{numIn(noSel.y, (v) => v !== null && updNo({ y: v }), "y")}</Campo>
            </div>
            {noSel.type === "captor" && (
              <div className="grade g2" style={{ marginTop: 8 }}>
                <Campo rotulo="Tipo de captor">
                  <select value={noSel.captor?.tipo || "vazao_informada"} disabled={!editavel} onChange={(e) => updCap({ tipo: e.target.value })}>
                    {Object.entries(TIPOS_CAPTOR).map(([k, r]) => <option key={k} value={k}>{r}</option>)}
                  </select>
                </Campo>
                <Campo rotulo="Entrada (perda)">
                  <select value={noSel.captor?.entrada || "flangeada"} disabled={!editavel} onChange={(e) => updCap({ entrada: e.target.value })}>
                    {Object.entries(ENTRADAS_CAPTOR).map(([k, r]) => <option key={k} value={k}>{r}</option>)}
                  </select>
                </Campo>
                {noSel.captor?.tipo === "vazao_informada" ? (
                  <Campo rotulo="Vazão (m³/h)">{numIn(noSel.captor?.vazao_m3h, (v) => updCap({ vazao_m3h: v }), "q")}</Campo>
                ) : (
                  <Campo rotulo="Processo / dispersão">
                    <select value={noSel.captor?.processo || ""} disabled={!editavel} onChange={(e) => updCap({ processo: e.target.value })}>
                      <option value="">—</option>
                      <option value="baixa_dispersao">Baixa dispersão</option>
                      <option value="media_dispersao">Média dispersão</option>
                      <option value="alta_dispersao">Alta dispersão</option>
                      <option value="solda">Solda</option>
                    </select>
                  </Campo>
                )}
                {["abertura_livre", "abertura_flangeada"].includes(noSel.captor?.tipo) && <>
                  <Campo rotulo="Distância à fonte X (m)">{numIn(noSel.captor?.distancia_m, (v) => updCap({ distancia_m: v }), "x")}</Campo>
                  <Campo rotulo="Área de face (m²)">{numIn(noSel.captor?.area_face_m2, (v) => updCap({ area_face_m2: v }), "a")}</Campo>
                </>}
                {noSel.captor?.tipo === "enclausuramento" && <Campo rotulo="Área aberta (m²)">{numIn(noSel.captor?.area_aberta_m2, (v) => updCap({ area_aberta_m2: v }), "aa")}</Campo>}
                {noSel.captor?.tipo === "coifa_baixa" && <>
                  <Campo rotulo="Perímetro (m)">{numIn(noSel.captor?.perimetro_m, (v) => updCap({ perimetro_m: v }), "p")}</Campo>
                  <Campo rotulo="Altura sobre a fonte (m)">{numIn(noSel.captor?.altura_m, (v) => updCap({ altura_m: v }), "h")}</Campo>
                  <label><input type="checkbox" checked={!!noSel.captor?.fonte_quente} disabled={!editavel} onChange={(e) => updCap({ fonte_quente: e.target.checked })} /> Fonte quente</label>
                </>}
              </div>
            )}
            {noSel.type === "filtro" && (
              <div className="grade g2" style={{ marginTop: 8 }}>
                <Campo rotulo="Tipo de filtro">
                  <select value={noSel.filtro_tipo || ""} disabled={!editavel} onChange={(e) => updNo({ filtro_tipo: e.target.value })}>
                    <option value="mangas">Mangas</option><option value="cartucho">Cartucho</option><option value="lavador">Lavador</option><option value="generico">Genérico</option>
                  </select>
                </Campo>
                <Campo rotulo="Perda informada (Pa)" dica="da folha de dados; vazio = parâmetro cadastrado">{numIn(noSel.perda_pa, (v) => updNo({ perda_pa: v }), "dp")}</Campo>
              </div>
            )}
          </Cartao>
        )}
        {trSel && (
          <Cartao titulo={`Trecho ${trSel.id}: ${trSel.from} → ${trSel.to}`}>
            <div className="grade g2">
              <Campo rotulo="Rótulo"><input value={trSel.label || ""} disabled={!editavel} onChange={(e) => updTr({ label: e.target.value })} /></Campo>
              <Campo rotulo="Forma">
                <select value={trSel.forma || "circular"} disabled={!editavel} onChange={(e) => updTr({ forma: e.target.value })}>
                  <option value="circular">Circular</option><option value="retangular">Retangular</option>
                </select>
              </Campo>
              {(trSel.forma || "circular") === "circular" ? (
                <Campo rotulo="Diâmetro fixo (mm)" dica="vazio = dimensionamento automático">{numIn(trSel.diametro_mm, (v) => updTr({ diametro_mm: v }), "d")}</Campo>
              ) : <>
                <Campo rotulo="Largura (mm)">{numIn(trSel.largura_mm, (v) => updTr({ largura_mm: v }), "w")}</Campo>
                <Campo rotulo="Altura (mm)">{numIn(trSel.altura_mm, (v) => updTr({ altura_mm: v }), "hh")}</Campo>
              </>}
              <Campo rotulo="Material">
                <select value={trSel.material || ""} disabled={!editavel} onChange={(e) => updTr({ material: e.target.value || undefined })}>
                  <option value="">Padrão do projeto</option><option value="galvanizado">Galvanizado</option><option value="aco_carbono">Aço carbono</option><option value="inox">Inox</option><option value="pvc">PVC</option>
                </select>
              </Campo>
              <Campo rotulo="Comprimento extra (m)" dica="trechos verticais">{numIn(trSel.comprimento_extra_m, (v) => updTr({ comprimento_extra_m: v }), "ce")}</Campo>
              <Campo rotulo="Curvas extras de 90° (qtd)">{numIn((trSel.curvas_extra || [])[0]?.qtd, (v) => updTr({ curvas_extra: v ? [{ angulo: 90, qtd: v }] : [] }), "cv")}</Campo>
            </div>
            <label style={{ display: "block", marginTop: 6 }}><input type="checkbox" checked={!!trSel.travado} disabled={!editavel} onChange={(e) => updTr({ travado: e.target.checked })} /> Travar trajeto (o roteamento automático não altera)</label>
            {editavel && (trSel.path || []).length > 0 && <button className="btn btn-mini" style={{ marginTop: 6 }} onClick={() => updTr({ path: [] })}>Limpar trajeto (linha reta)</button>}
            {trechosRes[trSel.id] && resAtual && (
              <p className="nota">Resultado: Ø{fmt(trechosRes[trSel.id].diametro_mm)} mm · {fmt(trechosRes[trSel.id].vazao_m3h)} m³/h · {fmt(trechosRes[trSel.id].velocidade_ms, 2)} m/s · L {fmt(trechosRes[trSel.id].comprimento_m, 2)} m · perda {fmt(trechosRes[trSel.id].perda_total_pa, 1)} Pa</p>
            )}
          </Cartao>
        )}
        {alts && (
          <Cartao titulo="Alternativas de dimensionamento">
            <table>
              <thead><tr><th>Critério</th><th className="num">P total (Pa)</th><th>Exaustor</th><th className="num">kW</th><th className="num">kWh/ano</th><th className="num">Materiais (R$)</th></tr></thead>
              <tbody>
                {alts.map((a) => (
                  <tr key={a.estrategia}>
                    <td>{a.nome}{a.erro && <div className="div-erro">{a.erro}</div>}</td>
                    <td className="num">{fmt(a.pressao_total_pa)}</td>
                    <td>{a.exaustor || <span className="div-erro">nenhum compatível</span>}</td>
                    <td className="num">{fmt(a.potencia_kw, 2)}</td>
                    <td className="num">{fmt(a.energia_kwh_ano)}</td>
                    <td className="num">{a.custo_materiais !== null && a.custo_materiais !== undefined ? fmt(a.custo_materiais, 2) : "—"}{a.itens_sem_custo ? ` (${a.itens_sem_custo} s/ custo)` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="nota">Custos somam apenas itens com preço cadastrado. Energia = potência × horas/ano informadas.</p>
          </Cartao>
        )}
      </div>
    </div>
  );
}
