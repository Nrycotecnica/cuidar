import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Grafico from "../components/Grafico";
import { Abas, Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox, Selo, SeloDemo } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmt, numero } from "../lib/format";
import { useCarregar } from "../lib/hooks";

function Importar({ url, modelo, aoConcluir }: { url: string; modelo: string; aoConcluir: () => void }) {
  const [r, setR] = useState<any>(null);
  const [erro, setErro] = useState<unknown>(null);
  return (
    <div className="form-linha">
      <Campo rotulo="Importar CSV/Excel">
        <input type="file" accept=".csv,.xlsx" onChange={async (e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          const fd = new FormData();
          fd.append("arquivo", f);
          setErro(null);
          try { setR(await api.enviar(url, fd)); aoConcluir(); } catch (er) { setErro(er); }
          e.target.value = "";
        }} />
      </Campo>
      <button className="btn btn-mini" onClick={() => api.baixar(`/modelos/${modelo}.csv`, `modelo_${modelo}.csv`)}>Baixar planilha modelo</button>
      <ErroBox erro={erro} />
      {r && <Alerta tipo={r.erros.length ? "aviso" : "ok"}>Criados: {r.criados.length} · atualizados: {r.atualizados.length}{r.erros.length > 0 && <ul>{r.erros.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>}</Alerta>}
    </div>
  );
}

const EX_VAZIO = { codigo: "", modelo: "", tipo: "centrifugo_radial", rotacao_rpm: "", potencia_motor_kw: "", temperatura_max_c: "", tipo_pressao_curva: "estatica", densidade_referencia: "1,2", preco: "", materiais: "", observacoes: "", curva: [{ vazao_m3h: "", pressao_pa: "", potencia_kw: "" }, { vazao_m3h: "", pressao_pa: "", potencia_kw: "" }] };

function FormExaustor({ inicial, aoSalvar, aoCancelar }: { inicial: any; aoSalvar: () => void; aoCancelar: () => void }) {
  const { pode } = useAuth();
  const [f, setF] = useState<any>(() => ({ ...inicial, curva: (inicial.curva || []).map((p: any) => ({ vazao_m3h: String(p.vazao_m3h ?? ""), pressao_pa: String(p.pressao_pa ?? ""), potencia_kw: p.potencia_kw != null ? String(p.potencia_kw) : "" })) }));
  const [erro, setErro] = useState<unknown>(null);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const tecnico = pode("catalogo.editar");
  const salvar = async () => {
    setErro(null);
    const n = (v: any) => (v === "" || v == null ? null : numero(String(v)));
    const curva = f.curva.filter((p: any) => p.vazao_m3h !== "" || p.pressao_pa !== "").map((p: any) => {
      const o: any = { vazao_m3h: n(p.vazao_m3h), pressao_pa: n(p.pressao_pa) };
      if (n(p.potencia_kw) != null) o.potencia_kw = n(p.potencia_kw);
      return o;
    });
    const corpo: any = tecnico ? {
      codigo: f.codigo, modelo: f.modelo, tipo: f.tipo, rotacao_rpm: n(f.rotacao_rpm), potencia_motor_kw: n(f.potencia_motor_kw), temperatura_max_c: n(f.temperatura_max_c),
      tipo_pressao_curva: f.tipo_pressao_curva, densidade_referencia: n(f.densidade_referencia) || 1.2, preco: n(f.preco), materiais: f.materiais, observacoes: f.observacoes, curva,
    } : { preco: n(f.preco) };
    try {
      if (f.id) await api.put(`/exaustores/${f.id}`, corpo);
      else await api.post("/exaustores", corpo);
      aoSalvar();
    } catch (e) { setErro(e); }
  };
  const pontos: [number, number][] = f.curva.map((p: any) => [numero(p.vazao_m3h), numero(p.pressao_pa)]).filter((p: any) => p[0] != null && p[1] != null);
  return (
    <Cartao titulo={f.id ? `Editar ${f.codigo}` : "Novo exaustor"}>
      {f.id && <Alerta tipo="info">Alterar dados técnicos retorna o equipamento ao status “proposto” (exige nova aprovação).</Alerta>}
      <div className="grade g4">
        <Campo rotulo="Código *"><input value={f.codigo} disabled={!tecnico || !!f.id} onChange={set("codigo")} /></Campo>
        <Campo rotulo="Modelo *"><input value={f.modelo} disabled={!tecnico} onChange={set("modelo")} /></Campo>
        <Campo rotulo="Tipo *">
          <select value={f.tipo} disabled={!tecnico} onChange={set("tipo")}>
            <option value="centrifugo_radial">Centrífugo pás radiais</option><option value="centrifugo_limite">Centrífugo limit-load</option>
            <option value="centrifugo">Centrífugo (outro)</option><option value="axial">Axial</option><option value="parede">Parede</option>
          </select>
        </Campo>
        <Campo rotulo="Rotação (rpm)"><input value={f.rotacao_rpm ?? ""} disabled={!tecnico} onChange={set("rotacao_rpm")} /></Campo>
        <Campo rotulo="Potência do motor (kW)"><input value={f.potencia_motor_kw ?? ""} disabled={!tecnico} onChange={set("potencia_motor_kw")} /></Campo>
        <Campo rotulo="Temperatura máx. (°C)"><input value={f.temperatura_max_c ?? ""} disabled={!tecnico} onChange={set("temperatura_max_c")} /></Campo>
        <Campo rotulo="Pressão da curva">
          <select value={f.tipo_pressao_curva} disabled={!tecnico} onChange={set("tipo_pressao_curva")}><option value="estatica">Estática</option><option value="total">Total</option></select>
        </Campo>
        <Campo rotulo="Densidade de referência (kg/m³)"><input value={f.densidade_referencia ?? ""} disabled={!tecnico} onChange={set("densidade_referencia")} /></Campo>
        <Campo rotulo="Preço (R$)"><input value={f.preco ?? ""} disabled={!(tecnico || pode("custos.editar"))} onChange={set("preco")} /></Campo>
        <Campo rotulo="Materiais"><input value={f.materiais ?? ""} disabled={!tecnico} onChange={set("materiais")} /></Campo>
      </div>
      <div className="grade g2" style={{ marginTop: 10 }}>
        <div>
          <h3>Curva de desempenho</h3>
          <table>
            <thead><tr><th>Vazão (m³/h)</th><th>Pressão (Pa)</th><th>Potência (kW)</th><th></th></tr></thead>
            <tbody>{f.curva.map((p: any, i: number) => (
              <tr key={i}>
                {["vazao_m3h", "pressao_pa", "potencia_kw"].map((k) => (
                  <td key={k}><input value={p[k]} disabled={!tecnico} onChange={(e) => setF({ ...f, curva: f.curva.map((q: any, j: number) => (j === i ? { ...q, [k]: e.target.value } : q)) })} /></td>
                ))}
                <td>{tecnico && <button className="btn btn-mini btn-perigo" onClick={() => setF({ ...f, curva: f.curva.filter((_: any, j: number) => j !== i) })}>×</button>}</td>
              </tr>
            ))}</tbody>
          </table>
          {tecnico && <button className="btn btn-mini" onClick={() => setF({ ...f, curva: [...f.curva, { vazao_m3h: "", pressao_pa: "", potencia_kw: "" }] })}>+ ponto</button>}
          <p className="nota">Mínimo de 2 pontos, vazões distintas. A seleção interpola linearmente e nunca extrapola fora da faixa cadastrada.</p>
        </div>
        <Grafico series={[{ nome: "Curva cadastrada", pontos: pontos.sort((a, b) => a[0] - b[0]), cor: "#1f4e79" }]} altura={260} />
      </div>
      <ErroBox erro={erro} />
      <div className="acoes"><BotaoAcao className="btn btn-primario" onClick={salvar}>Salvar</BotaoAcao><button className="btn" onClick={aoCancelar}>Cancelar</button></div>
    </Cartao>
  );
}

function ConsultaCurva({ ex }: { ex: any }) {
  const [t, setT] = useState("20");
  const [h, setH] = useState("0");
  const [q, setQ] = useState("");
  const [r, setR] = useState<any>(null);
  const [erro, setErro] = useState<unknown>(null);
  const consultar = async () => {
    setErro(null);
    const qs = new URLSearchParams({ temperatura_c: String(numero(t) ?? 20), altitude_m: String(numero(h) ?? 0) });
    if (numero(q) != null) qs.set("vazao_m3h", String(numero(q)));
    try { setR(await api.get(`/exaustores/${ex.id}/curva?${qs}`)); } catch (e) { setErro(e); }
  };
  useEffect(() => { consultar(); /* eslint-disable-next-line */ }, [ex.id]);
  return (
    <Cartao titulo={`Consulta da curva — ${ex.codigo}`}>
      <div className="form-linha">
        <Campo rotulo="Temperatura (°C)"><input value={t} onChange={(e) => setT(e.target.value)} style={{ width: 90 }} /></Campo>
        <Campo rotulo="Altitude (m)"><input value={h} onChange={(e) => setH(e.target.value)} style={{ width: 90 }} /></Campo>
        <Campo rotulo="Vazão (m³/h)"><input value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 110 }} /></Campo>
        <BotaoAcao className="btn" onClick={consultar}>Consultar</BotaoAcao>
      </div>
      <ErroBox erro={erro} />
      {r && <>
        <p>Densidade {fmt(r.densidade, 4)} kg/m³ · fator de correção {fmt(r.fator_densidade, 3)} · faixa válida {fmt(r.faixa_m3h[0])}–{fmt(r.faixa_m3h[1])} m³/h</p>
        {r.consulta && <Alerta tipo={r.consulta.pressao_pa != null ? "ok" : "aviso"}>{r.consulta.pressao_pa != null ? `Em ${fmt(r.consulta.vazao_m3h)} m³/h: ${fmt(r.consulta.pressao_pa)} Pa (${r.tipo_pressao === "estatica" ? "estática" : "total"}, corrigida)` : r.consulta.mensagem}</Alerta>}
        <Grafico series={[{ nome: "Curva corrigida", pontos: r.pontos.map((p: any) => [p.vazao_m3h, p.pressao_pa]), cor: "#1f4e79" }]}
          marcador={r.consulta?.pressao_pa != null ? { x: r.consulta.vazao_m3h, y: r.consulta.pressao_pa, rotulo: "consulta" } : null} altura={260} />
      </>}
    </Cartao>
  );
}

function Exaustores() {
  const { pode } = useAuth();
  const { dados, erro, recarregar } = useCarregar(() => api.get<any[]>("/exaustores"));
  const [form, setForm] = useState<any>(null);
  const [consulta, setConsulta] = useState<any>(null);
  const [erroA, setErroA] = useState<unknown>(null);
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  return (
    <div>
      {form && <FormExaustor key={form.id || "novo"} inicial={form} aoCancelar={() => setForm(null)} aoSalvar={() => { setForm(null); recarregar(); }} />}
      {consulta && <ConsultaCurva ex={consulta} />}
      <Cartao titulo={`Exaustores (${dados.length})`} acoes={pode("catalogo.editar") && <button className="btn btn-primario" onClick={() => setForm({ ...EX_VAZIO })}>Novo exaustor</button>}>
        {pode("catalogo.editar") && <Importar url="/exaustores/importar" modelo="exaustores" aoConcluir={recarregar} />}
        <ErroBox erro={erroA} />
        <table style={{ marginTop: 8 }}>
          <thead><tr><th>Código</th><th>Modelo</th><th>Tipo</th><th className="num">rpm</th><th className="num">Motor kW</th><th className="num">Faixa (m³/h)</th><th className="num">T máx</th><th>Status</th><th className="num">Preço</th><th></th></tr></thead>
          <tbody>{dados.map((e) => {
            const qs = (e.curva || []).map((p: any) => p.vazao_m3h);
            return (
              <tr key={e.id}>
                <td><code>{e.codigo}</code></td><td>{e.modelo} <SeloDemo ativo={e.demonstrativo} /></td><td>{e.tipo}</td>
                <td className="num">{fmt(e.rotacao_rpm)}</td><td className="num">{fmt(e.potencia_motor_kw, 1)}</td>
                <td className="num">{qs.length ? `${fmt(Math.min(...qs))}–${fmt(Math.max(...qs))}` : "—"}</td><td className="num">{fmt(e.temperatura_max_c)}</td>
                <td>{e.status === "aprovado" ? <Selo tipo="ok">aprovado</Selo> : <Selo tipo="aviso">proposto</Selo>}</td>
                <td className="num">{e.preco != null ? fmt(e.preco, 2) : "—"}</td>
                <td><div className="acoes">
                  <button className="btn btn-mini" onClick={() => setConsulta(e)}>Curva</button>
                  {(pode("catalogo.editar") || pode("custos.editar")) && <button className="btn btn-mini" onClick={() => setForm(e)}>Editar</button>}
                  {pode("parametros.aprovar") && e.status !== "aprovado" && !e.demonstrativo && (
                    <BotaoAcao className="btn btn-mini btn-ok" confirmar={`Aprovar os dados técnicos do exaustor ${e.codigo}?`} onClick={async () => { try { await api.post(`/exaustores/${e.id}/aprovar`); recarregar(); } catch (er) { setErroA(er); } }}>Aprovar</BotaoAcao>
                  )}
                </div></td>
              </tr>
            );
          })}</tbody>
        </table>
      </Cartao>
    </div>
  );
}

const CAMPOS_COMP: [string, string][] = [["codigo", "Código *"], ["descricao", "Descrição *"], ["diametro_mm", "Ø (mm)"], ["diametro2_mm", "Ø2 (mm)"], ["largura_mm", "Largura (mm)"], ["altura_mm", "Altura (mm)"], ["espessura_mm", "Espessura (mm)"], ["material", "Material"], ["comprimento_m", "Comprimento (m)"], ["angulo_graus", "Ângulo (°)"], ["massa_kg", "Massa (kg)"], ["unidade", "Unidade"], ["custo_unitario", "Custo unitário (R$)"]];
const NUM_COMP = new Set(["diametro_mm", "diametro2_mm", "largura_mm", "altura_mm", "espessura_mm", "comprimento_m", "angulo_graus", "massa_kg", "custo_unitario"]);

function Componentes() {
  const { pode } = useAuth();
  const { dados, erro, recarregar } = useCarregar(() => Promise.all([api.get<any[]>("/componentes"), api.get<Record<string, string>>("/componentes/categorias")]));
  const [cat, setCat] = useState("");
  const [form, setForm] = useState<any>(null);
  const [erroF, setErroF] = useState<unknown>(null);
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  const [comps, cats] = dados;
  const lista = comps.filter((c) => !cat || c.categoria === cat);
  const salvar = async () => {
    setErroF(null);
    const corpo: any = { categoria: form.categoria, forma: form.forma || "circular" };
    for (const [k] of CAMPOS_COMP) corpo[k] = NUM_COMP.has(k) ? numero(form[k] === undefined ? null : String(form[k] ?? "")) : form[k] || null;
    try {
      if (form.id) await api.put(`/componentes/${form.id}`, pode("catalogo.editar") ? corpo : { custo_unitario: corpo.custo_unitario });
      else await api.post("/componentes", corpo);
      setForm(null);
      recarregar();
    } catch (e) { setErroF(e); }
  };
  return (
    <div>
      {form && (
        <Cartao titulo={form.id ? `Editar ${form.codigo}` : "Novo componente"}>
          <div className="grade g4">
            <Campo rotulo="Categoria *">
              <select value={form.categoria} disabled={!!form.id} onChange={(e) => setForm({ ...form, categoria: e.target.value })}>
                {Object.entries(cats).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Campo>
            {CAMPOS_COMP.map(([k, r]) => (
              <Campo key={k} rotulo={r}><input value={form[k] ?? ""} disabled={(k === "codigo" && !!form.id) || (!pode("catalogo.editar") && k !== "custo_unitario")} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></Campo>
            ))}
          </div>
          <ErroBox erro={erroF} />
          <div className="acoes" style={{ marginTop: 8 }}><BotaoAcao className="btn btn-primario" onClick={salvar}>Salvar</BotaoAcao><button className="btn" onClick={() => setForm(null)}>Cancelar</button></div>
        </Cartao>
      )}
      <Cartao titulo={`Componentes de dutos (${lista.length})`} acoes={<>
        <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ width: 200 }}>
          <option value="">Todas as categorias</option>
          {Object.entries(cats).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        {pode("catalogo.editar") && <button className="btn btn-primario" onClick={() => setForm({ categoria: "duto_circular", unidade: "un" })}>Novo componente</button>}
      </>}>
        {pode("catalogo.editar") && <Importar url="/componentes/importar" modelo="componentes" aoConcluir={recarregar} />}
        <div className="tabela-rolagem" style={{ marginTop: 8 }}>
          <table>
            <thead><tr><th>Código</th><th>Categoria</th><th>Descrição</th><th className="num">Ø</th><th className="num">Ø2</th><th className="num">Esp.</th><th>Material</th><th className="num">Compr.</th><th className="num">Âng.</th><th className="num">Custo</th><th></th></tr></thead>
            <tbody>{lista.map((c) => (
              <tr key={c.id}>
                <td><code>{c.codigo}</code></td><td>{cats[c.categoria] || c.categoria}</td><td>{c.descricao} <SeloDemo ativo={c.demonstrativo} /></td>
                <td className="num">{fmt(c.diametro_mm)}</td><td className="num">{fmt(c.diametro2_mm)}</td><td className="num">{fmt(c.espessura_mm, 2)}</td>
                <td>{c.material}</td><td className="num">{fmt(c.comprimento_m, 2)}</td><td className="num">{fmt(c.angulo_graus)}</td>
                <td className="num">{c.custo_unitario != null ? fmt(c.custo_unitario, 2) : "—"}</td>
                <td>{(pode("catalogo.editar") || pode("custos.editar")) && <button className="btn btn-mini" onClick={() => setForm(c)}>Editar</button>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </Cartao>
    </div>
  );
}

function Parametros() {
  const { pode } = useAuth();
  const { dados, erro, recarregar } = useCarregar(() => api.get<any[]>("/parametros"));
  const [edit, setEdit] = useState<any>(null);
  const [novo, setNovo] = useState<any>(null);
  const [erroP, setErroP] = useState<unknown>(null);
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  const porCat: Record<string, any[]> = {};
  for (const p of dados) (porCat[p.categoria] ||= []).push(p);
  const valorDe = (s: string) => { const n = numero(s); return n === null ? s : n; };
  return (
    <div>
      <Alerta tipo="aviso">Parâmetros dependentes de normas, materiais e contaminantes. Valores <strong>demonstrativos</strong> precisam ser revisados com referência técnica e aprovados por responsável técnico antes de qualquer projeto real. A IA nunca altera esses valores.</Alerta>
      <ErroBox erro={erroP} />
      {pode("parametros.editar") && !novo && <button className="btn btn-primario" onClick={() => setNovo({ chave: "", valor: "", unidade: "", categoria: "", descricao: "", referencia: "" })}>Novo parâmetro</button>}
      {novo && (
        <Cartao titulo="Novo parâmetro">
          <div className="grade g3">
            {["chave", "valor", "unidade", "categoria", "descricao", "referencia"].map((k) => <Campo key={k} rotulo={k === "referencia" ? "Referência técnica *" : k[0].toUpperCase() + k.slice(1)}><input value={novo[k]} onChange={(e) => setNovo({ ...novo, [k]: e.target.value })} /></Campo>)}
          </div>
          <div className="acoes" style={{ marginTop: 8 }}>
            <BotaoAcao className="btn btn-primario" onClick={async () => { setErroP(null); try { await api.post("/parametros", { ...novo, valor: valorDe(novo.valor) }); setNovo(null); recarregar(); } catch (e) { setErroP(e); } }}>Salvar</BotaoAcao>
            <button className="btn" onClick={() => setNovo(null)}>Cancelar</button>
          </div>
        </Cartao>
      )}
      {Object.entries(porCat).map(([cat, ps]) => (
        <Cartao key={cat} titulo={cat}>
          <table>
            <thead><tr><th>Chave</th><th className="num">Valor</th><th>Unid.</th><th>Referência</th><th>Status</th><th></th></tr></thead>
            <tbody>{ps.map((p) => edit?.id === p.id ? (
              <tr key={p.id}>
                <td><code>{p.chave}</code></td>
                <td><input value={edit.valor} onChange={(e) => setEdit({ ...edit, valor: e.target.value })} /></td>
                <td><input value={edit.unidade} onChange={(e) => setEdit({ ...edit, unidade: e.target.value })} /></td>
                <td><input value={edit.referencia} onChange={(e) => setEdit({ ...edit, referencia: e.target.value })} placeholder="norma, literatura, ensaio" /></td>
                <td colSpan={2}><div className="acoes">
                  <BotaoAcao className="btn btn-mini btn-primario" onClick={async () => {
                    setErroP(null);
                    if (p.demonstrativo && !edit.referencia.trim()) { setErroP("Informe a referência técnica (norma, literatura ou ensaio) para substituir o valor demonstrativo."); return; }
                    const corpo: any = { valor: valorDe(String(edit.valor)), unidade: edit.unidade };
                    if (edit.referencia.trim()) corpo.referencia = edit.referencia.trim();
                    try { await api.put(`/parametros/${p.id}`, corpo); setEdit(null); recarregar(); } catch (e) { setErroP(e); }
                  }}>Salvar</BotaoAcao>
                  <button className="btn btn-mini" onClick={() => setEdit(null)}>Cancelar</button>
                </div></td>
              </tr>
            ) : (
              <tr key={p.id}>
                <td><code>{p.chave}</code></td><td className="num">{typeof p.valor === "number" ? fmt(p.valor, 4).replace(/,?0+$/, "") : JSON.stringify(p.valor)}</td><td>{p.unidade}</td>
                <td className="nota">{p.referencia}</td>
                <td>{p.status === "aprovado" ? <Selo tipo="ok">aprovado</Selo> : <Selo tipo="aviso">proposto</Selo>} <SeloDemo ativo={p.demonstrativo} /></td>
                <td><div className="acoes">
                  {pode("parametros.editar") && <button className="btn btn-mini" onClick={() => setEdit({ id: p.id, valor: String(p.valor).replace(".", ","), unidade: p.unidade || "", referencia: p.demonstrativo ? "" : p.referencia || "" })}>Editar</button>}
                  {pode("parametros.aprovar") && p.status !== "aprovado" && !p.demonstrativo && (
                    <BotaoAcao className="btn btn-mini btn-ok" confirmar={`Aprovar ${p.chave} = ${p.valor} ${p.unidade || ""}?`} onClick={async () => { setErroP(null); try { await api.post(`/parametros/${p.id}/aprovar`); recarregar(); } catch (e) { setErroP(e); } }}>Aprovar</BotaoAcao>
                  )}
                </div></td>
              </tr>
            ))}</tbody>
          </table>
        </Cartao>
      ))}
    </div>
  );
}

export default function Catalogo() {
  const { aba = "exaustores" } = useParams();
  const nav = useNavigate();
  return (
    <div>
      <div className="cabecalho"><div><h1>Catálogo técnico</h1><div className="sub">Equipamentos fabricados pela empresa, componentes de dutos e parâmetros de engenharia</div></div></div>
      <Abas abas={[{ id: "exaustores", rotulo: "Exaustores" }, { id: "componentes", rotulo: "Componentes de dutos" }, { id: "parametros", rotulo: "Parâmetros técnicos" }]} ativa={aba} onChange={(a) => nav(`/catalogo/${a}`)} />
      {aba === "exaustores" && <Exaustores />}
      {aba === "componentes" && <Componentes />}
      {aba === "parametros" && <Parametros />}
    </div>
  );
}
