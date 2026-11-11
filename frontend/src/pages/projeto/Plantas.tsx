import { useEffect, useMemo, useRef, useState } from "react";
import CanvasView, { escalaGrafica } from "../../components/CanvasView";
import { Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox, Selo } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { desenharEntidades, linhaCota, marcaPonto, poligono } from "../../lib/desenho";
import { dataHora, fmt, numero } from "../../lib/format";
import { dist, pontoEmPoligono, retangulo, type Pt } from "../../lib/geom";
import type { CtxProjeto } from "./Projeto";

type Ferramenta = "navegar" | "medir" | "calibrar" | "pilar" | "maquina" | "excluir";

function Visualizador({ planta, aoAtualizar, editavel }: { planta: any; aoAtualizar: () => void; editavel: boolean }) {
  const g = planta.geometria || {};
  const camadas: any[] = g.camadas || [];
  const [ocultas, setOcultas] = useState<Set<number>>(new Set());
  const [mostrarDet, setMostrarDet] = useState(true);
  const [ferr, setFerr] = useState<Ferramenta>("navegar");
  const [pts, setPts] = useState<Pt[]>([]);
  const [mouse, setMouse] = useState<Pt | null>(null);
  const [distReal, setDistReal] = useState("");
  const [escalaManual, setEscalaManual] = useState("");
  const [det, setDet] = useState<any>(planta.deteccoes || {});
  const [detAlterada, setDetAlterada] = useState(false);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [erro, setErro] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const esc: number | null = planta.escala_m_por_unidade;
  const confirmada: boolean = planta.escala_confirmada;
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    setDet(planta.deteccoes || {});
    setDetAlterada(false);
    setPts([]);
  }, [planta]);
  useEffect(() => {
    let ativo = true;
    if (planta.imagem_arquivo_id) {
      api.blob(`/arquivos/${planta.imagem_arquivo_id}/download`).then((b) => {
        if (!ativo) return;
        const url = URL.createObjectURL(b);
        urlRef.current = url;
        const im = new Image();
        im.onload = () => ativo && setImg(im);
        im.src = url;
      }).catch(() => {});
    } else setImg(null);
    return () => {
      ativo = false;
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, [planta.imagem_arquivo_id]);

  const ext = g.extensao as [number, number, number, number] | null;
  // detecções estão em metros → converter para unidades do desenho
  const k = esc ? 1 / esc : null;
  const conv = (p: number[][]) => (k ? p.map(([x, y]) => [x * k, y * k]) : p);
  const unidade = planta.unidade_original || "un";

  const medida = (a: Pt, b: Pt) => {
    const d = dist(a, b);
    if (esc) return `${fmt(d * esc, 3)} m${confirmada ? "" : " (escala NÃO confirmada)"}`;
    return `${fmt(d, 2)} ${unidade} (sem escala)`;
  };

  const desenhar = (ctx: CanvasRenderingContext2D, v: any) => {
    if (img && g.imagem) {
      const W = g.imagem.largura, H = g.imagem.altura;
      const sx = (0 - v.cx) * v.escala + v.w / 2;
      const sy = v.h / 2 - (H - v.cy) * v.escala;
      ctx.globalAlpha = 0.85;
      ctx.drawImage(img, sx, sy, W * v.escala, H * v.escala);
      ctx.globalAlpha = 1;
    }
    desenharEntidades(ctx, v, g.entidades || [], camadas, ocultas);
    if (mostrarDet && k) {
      if (det.contorno?.pontos) poligono(ctx, v, conv(det.contorno.pontos), null, "#1565c0", 2, [10, 6]);
      for (const p of det.pilares || []) poligono(ctx, v, conv(p.pontos), "rgba(90,90,90,.55)", "#333", 1.5);
      for (const m of det.maquinas || []) poligono(ctx, v, conv(m.pontos), "rgba(255,152,0,.25)", "#e65100", 1.5);
    }
    if (pts.length === 1 && mouse && (ferr === "medir" || ferr === "calibrar")) linhaCota(ctx, v, pts[0], mouse, medida(pts[0], mouse));
    if (pts.length === 2 && (ferr === "medir" || ferr === "calibrar")) linhaCota(ctx, v, pts[0], pts[1], medida(pts[0], pts[1]), ferr === "calibrar" ? "#1565c0" : "#c00");
    if (pts.length === 1 && mouse && (ferr === "pilar" || ferr === "maquina")) poligono(ctx, v, retangulo(pts[0], mouse), "rgba(21,101,192,.15)", "#1565c0", 1.5, [5, 4]);
    pts.forEach((p) => marcaPonto(ctx, v, p, "#c00"));
    escalaGrafica(ctx, v, esc ? 1 / esc : null);
  };

  const clicar = ({ p }: { p: Pt }) => {
    if (ferr === "medir" || ferr === "calibrar") {
      setPts(pts.length >= 2 ? [p] : [...pts, p]);
    } else if (ferr === "pilar" || ferr === "maquina") {
      if (!esc) {
        setErro("Defina a escala antes de desenhar elementos.");
        return;
      }
      if (!pts.length) setPts([p]);
      else {
        const r = retangulo(pts[0], p).map(([x, y]) => [x * esc, y * esc]);
        const chave = ferr === "pilar" ? "pilares" : "maquinas";
        setDet({ ...det, [chave]: [...(det[chave] || []), { pontos: r, confianca: 1, manual: true, nome: ferr === "maquina" ? "Obstáculo" : undefined }] });
        setDetAlterada(true);
        setPts([]);
      }
    } else if (ferr === "excluir" && k) {
      for (const chave of ["pilares", "maquinas"]) {
        const idx = (det[chave] || []).findIndex((x: any) => pontoEmPoligono(p, conv(x.pontos) as Pt[]));
        if (idx >= 0) {
          setDet({ ...det, [chave]: det[chave].filter((_: any, i: number) => i !== idx) });
          setDetAlterada(true);
          return;
        }
      }
    }
  };

  const calibrar = async () => {
    setErro(null);
    const d = numero(distReal);
    if (pts.length !== 2 || !d) {
      setErro("Marque dois pontos no desenho e informe a distância real em metros.");
      return;
    }
    try {
      await api.put(`/plantas/${planta.id}/escala`, { p1: pts[0], p2: pts[1], distancia_m: d, confirmar: true });
      setMsg("Escala calibrada e confirmada.");
      setPts([]);
      setFerr("navegar");
      aoAtualizar();
    } catch (e) { setErro(e); }
  };

  return (
    <div className="lado-a-lado">
      <div>
        <div className="ferramentas">
          {([["navegar", "Navegar"], ["medir", "Medir"], ["calibrar", "Calibrar escala"], ["pilar", "Desenhar pilar"], ["maquina", "Desenhar máquina/obstáculo"], ["excluir", "Excluir item detectado"]] as [Ferramenta, string][])
            .filter(([f]) => editavel || f === "navegar" || f === "medir")
            .map(([f, r]) => (
              <button key={f} className={ferr === f ? "btn btn-mini ativo" : "btn btn-mini"} onClick={() => { setFerr(f); setPts([]); }}>{r}</button>
            ))}
        </div>
        <CanvasView
          idTeste="visualizador-planta"
          extensao={ext}
          desenhar={desenhar}
          aoClicar={clicar}
          aoMover={(e) => setMouse(e.p)}
          cursor={ferr === "navegar" ? "grab" : "crosshair"}
          unidade={unidade}
        />
        <p className="nota">Roda do mouse: zoom no cursor · arrastar: mover a vista · {ferr === "medir" && "Medir: clique em dois pontos."}{ferr === "calibrar" && "Calibrar: clique em dois pontos de distância conhecida."}{(ferr === "pilar" || ferr === "maquina") && "Clique em dois cantos opostos."}{ferr === "excluir" && "Clique sobre um pilar/máquina detectado para excluí-lo."}</p>
      </div>
      <div className="pilha">
        <Cartao titulo="Escala">
          {esc ? (
            <p>1 {unidade} = <strong>{fmt(esc, 6)} m</strong> {confirmada ? <Selo tipo="ok">confirmada</Selo> : <Selo tipo="erro">não confirmada</Selo>}</p>
          ) : <p><Selo tipo="erro">sem escala</Selo></p>}
          {!confirmada && <Alerta tipo="aviso">Sem escala confirmada, as medidas desta planta <strong>não entram nos cálculos</strong>.</Alerta>}
          {planta.escala_info?.fonte && <p className="nota">Origem: {planta.escala_info.fonte}{planta.escala_info.por ? ` · por ${planta.escala_info.por}` : ""}</p>}
          {editavel && esc && !confirmada && (
            <BotaoAcao className="btn btn-mini btn-ok" onClick={async () => {
              try { await api.put(`/plantas/${planta.id}/escala`, { escala_m_por_unidade: esc, confirmar: true, fonte: "Escala declarada conferida pelo usuário" }); aoAtualizar(); } catch (e) { setErro(e); }
            }}>Confirmar escala declarada</BotaoAcao>
          )}
          {editavel && planta.sugestao_escala && !confirmada && (
            <div style={{ marginTop: 6 }}>
              <p className="nota">Texto encontrado no PDF: “{planta.sugestao_escala.texto}” → 1 pt = {fmt(planta.sugestao_escala.escala_m_por_unidade, 5)} m (válido somente se o PDF foi gerado sem redimensionamento).</p>
              <BotaoAcao className="btn btn-mini" onClick={async () => {
                try { await api.put(`/plantas/${planta.id}/escala`, { escala_m_por_unidade: planta.sugestao_escala.escala_m_por_unidade, confirmar: true, fonte: `Indicação "${planta.sugestao_escala.texto}" conferida pelo usuário` }); aoAtualizar(); } catch (e) { setErro(e); }
              }}>Usar e confirmar esta escala</BotaoAcao>
            </div>
          )}
          {editavel && ferr === "calibrar" && (
            <div className="form-linha" style={{ marginTop: 8 }}>
              <Campo rotulo="Distância real entre os pontos (m)"><input value={distReal} onChange={(e) => setDistReal(e.target.value)} inputMode="decimal" /></Campo>
              <BotaoAcao className="btn btn-primario btn-mini" onClick={calibrar} disabled={pts.length !== 2}>Calibrar</BotaoAcao>
            </div>
          )}
          {editavel && (
            <div className="form-linha" style={{ marginTop: 8 }}>
              <Campo rotulo={`Informar escala (m por ${unidade})`}><input value={escalaManual} onChange={(e) => setEscalaManual(e.target.value)} inputMode="decimal" placeholder="ex.: 0,001" /></Campo>
              <BotaoAcao className="btn btn-mini" onClick={async () => {
                const v = numero(escalaManual);
                if (!v) { setErro("Escala inválida"); return; }
                try { await api.put(`/plantas/${planta.id}/escala`, { escala_m_por_unidade: v, confirmar: true, fonte: "informada pelo usuário" }); aoAtualizar(); } catch (e) { setErro(e); }
              }}>Aplicar</BotaoAcao>
            </div>
          )}
        </Cartao>
        <Cartao titulo="Elementos identificados">
          <label><input type="checkbox" checked={mostrarDet} onChange={(e) => setMostrarDet(e.target.checked)} /> Mostrar detecções</label>
          <ul>
            <li>Contorno: {det.contorno ? `${fmt(det.contorno.area_m2, 1)} m² (confiança ${fmt((det.contorno.confianca || 0) * 100)}%)` : "—"}</li>
            <li>Pilares: {(det.pilares || []).length}</li>
            <li>Máquinas/obstáculos: {(det.maquinas || []).length}</li>
            <li>Pé-direito: {det.pe_direito_m ? `${fmt(det.pe_direito_m.valor_m, 2)} m (texto “${det.pe_direito_m.texto}”)` : "não encontrado"}</li>
          </ul>
          {(det.avisos || []).map((a: string, i: number) => <p key={i} className="nota">{a}</p>)}
          {editavel && (
            <div className="acoes">
              <BotaoAcao className="btn btn-mini" disabled={!detAlterada} onClick={async () => {
                try { await api.put(`/plantas/${planta.id}/deteccoes`, det); setDetAlterada(false); setMsg("Correções salvas."); } catch (e) { setErro(e); }
              }}>Salvar correções</BotaoAcao>
              <BotaoAcao className="btn btn-mini btn-primario" disabled={!confirmada || detAlterada} title={!confirmada ? "Confirme a escala primeiro" : detAlterada ? "Salve as correções primeiro" : ""} onClick={async () => {
                try { await api.post(`/plantas/${planta.id}/aplicar-ambiente`); setMsg("Contorno, pilares e obstáculos copiados para o ambiente do projeto (dimensões como 'estimado')."); } catch (e) { setErro(e); }
              }}>Usar no ambiente do projeto</BotaoAcao>
            </div>
          )}
        </Cartao>
        <ErroBox erro={erro} />
        {msg && <Alerta tipo="ok">{msg}</Alerta>}
        <Cartao titulo={`Camadas (${camadas.length})`}>
          <div style={{ maxHeight: 220, overflow: "auto" }}>
            {camadas.map((c, i) => (
              <label key={i} style={{ display: "block" }}>
                <input type="checkbox" checked={!ocultas.has(i)} onChange={() => { const n = new Set(ocultas); if (n.has(i)) n.delete(i); else n.add(i); setOcultas(n); }} />{" "}
                <span style={{ color: "#555" }}>■</span> {c.nome}
              </label>
            ))}
          </div>
        </Cartao>
        {(g.avisos || []).length > 0 && <Cartao titulo="Avisos da importação">{g.avisos.map((a: string, i: number) => <p key={i} className="nota">{a}</p>)}</Cartao>}
      </div>
    </div>
  );
}

export default function Plantas({ ctx }: { ctx: CtxProjeto }) {
  const { pode } = useAuth();
  const pid = ctx.projeto.id;
  const editavel = pode("projetos.editar") && !["aprovado", "liberado_fabricacao"].includes(ctx.projeto.status);
  const [lista, setLista] = useState<any[] | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [planta, setPlanta] = useState<any>(null);
  const [erro, setErro] = useState<unknown>(null);
  const [pagina, setPagina] = useState("1");
  const carregarLista = async () => {
    const l = await api.get<any[]>(`/projetos/${pid}/plantas`);
    setLista(l);
    return l;
  };
  const carregarPlanta = async (id: number) => setPlanta(await api.get(`/plantas/${id}`));
  useEffect(() => {
    carregarLista().then((l) => { if (l[0]) setSel(l[0].id); }).catch(setErro);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);
  useEffect(() => {
    if (sel) carregarPlanta(sel).catch(setErro);
  }, [sel]);
  const visor = useMemo(() => planta && <Visualizador planta={planta} editavel={editavel} aoAtualizar={() => { carregarPlanta(planta.id); carregarLista(); }} />, [planta, editavel]);
  if (!lista) return <Carregando />;
  return (
    <div>
      <Cartao titulo="Importar planta ou projeto" acoes={null}>
        {editavel ? (
          <div className="form-linha">
            <Campo rotulo="Arquivo (DXF, DWG, PDF, PNG, JPG)">
              <input type="file" accept=".dxf,.dwg,.pdf,.png,.jpg,.jpeg" onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                setErro(null);
                const fd = new FormData();
                fd.append("arquivo", f);
                fd.append("pagina", String(numero(pagina) || 1));
                try {
                  const r = await api.enviar(`/projetos/${pid}/plantas`, fd);
                  await carregarLista();
                  setSel(r.id);
                } catch (er) { setErro(er); }
                e.target.value = "";
              }} />
            </Campo>
            <Campo rotulo="Página do PDF"><input style={{ width: 80 }} value={pagina} onChange={(e) => setPagina(e.target.value)} /></Campo>
          </div>
        ) : <p className="nota">Sem permissão para importar.</p>}
        <p className="nota">DWG precisa de conversor configurado no servidor; caso contrário, exporte como DXF no AutoCAD. PDFs e imagens exigem calibração de escala antes do uso nos cálculos.</p>
        <ErroBox erro={erro} />
        {lista.length > 0 && (
          <table style={{ marginTop: 8 }}>
            <thead><tr><th>Planta</th><th>Origem</th><th className="num">Entidades</th><th>Escala</th><th>Importada</th></tr></thead>
            <tbody>
              {lista.map((p) => (
                <tr key={p.id} className={p.id === sel ? "clicavel selecionada" : "clicavel"} onClick={() => setSel(p.id)}>
                  <td>{p.nome}</td><td>{p.origem.toUpperCase()}</td><td className="num">{p.n_entidades}</td>
                  <td>{p.escala_confirmada ? <Selo tipo="ok">confirmada</Selo> : <Selo tipo="erro">não confirmada</Selo>}</td>
                  <td>{dataHora(p.criado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Cartao>
      {planta ? visor : lista.length ? <Carregando /> : <div className="vazio">Nenhuma planta importada. É possível trabalhar só com medidas manuais (aba Dados e Rede).</div>}
    </div>
  );
}
