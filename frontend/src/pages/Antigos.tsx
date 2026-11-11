import { useEffect, useState } from "react";
import { Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox, Selo } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dataHora, fmt, MODULOS, numero } from "../lib/format";
import { useCarregar } from "../lib/hooks";

const CONF: Record<string, string> = { nao_verificado: "Não verificado", conferido: "Conferido por engenheiro", medido_em_campo: "Desempenho medido em campo" };
const DADOS: [string, string][] = [["vazao_total_m3h", "Vazão total (m³/h)"], ["pressao_total_pa", "Pressão total (Pa)"], ["pressao_estatica_pa", "Pressão estática (Pa)"], ["potencia_kw", "Potência (kW)"], ["comprimento_total_m", "Comprimento de dutos (m)"], ["numero_captores", "Nº de captores"]];
const NOMES_GRANDEZA: Record<string, string> = { vazao_total_m3h: "Vazão total (m³/h)", pressao_total_pa: "Pressão total (Pa)", pressao_estatica_pa: "Pressão estática (Pa)", potencia_kw: "Potência (kW)", comprimento_dutos_m: "Comprimento de dutos (m)", numero_captores: "Nº de captores" };

function Form({ inicial, aoSalvar, aoCancelar }: { inicial: any; aoSalvar: () => void; aoCancelar: () => void }) {
  const d0 = inicial.dados || {};
  const [f, setF] = useState<any>({ ...inicial, ano: inicial.ano ?? "", dados: { ...Object.fromEntries(DADOS.map(([k]) => [k, d0[k] != null ? String(d0[k]).replace(".", ",") : ""])), exaustor: d0.exaustor || "", diametros_mm: (d0.diametros_mm || []).join("; ") } });
  const [erro, setErro] = useState<unknown>(null);
  const setD = (k: string) => (e: any) => setF({ ...f, dados: { ...f.dados, [k]: e.target.value } });
  const salvar = async () => {
    const dados: any = { exaustor: f.dados.exaustor || null };
    for (const [k] of DADOS) dados[k] = numero(f.dados[k]);
    dados.diametros_mm = String(f.dados.diametros_mm || "").split(/[;\s]+/).map((x: string) => numero(x)).filter((x: number | null) => x != null);
    const corpo = { nome: f.nome, cliente: f.cliente, ano: numero(String(f.ano)), modulo: f.modulo || null, descricao: f.descricao, desempenho_real: f.desempenho_real, confiabilidade: f.confiabilidade || "nao_verificado", dados };
    try {
      if (f.id) await api.put(`/antigos/${f.id}`, corpo);
      else await api.post("/antigos", corpo);
      aoSalvar();
    } catch (e) { setErro(e); }
  };
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return (
    <Cartao titulo={f.id ? `Editar: ${f.nome}` : "Novo projeto anterior"}>
      <div className="grade g4">
        <Campo rotulo="Nome *"><input value={f.nome || ""} onChange={set("nome")} /></Campo>
        <Campo rotulo="Cliente"><input value={f.cliente || ""} onChange={set("cliente")} /></Campo>
        <Campo rotulo="Ano"><input value={f.ano} onChange={set("ano")} /></Campo>
        <Campo rotulo="Sistema">
          <select value={f.modulo || ""} onChange={set("modulo")}><option value="">—</option>{Object.entries(MODULOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </Campo>
      </div>
      <Campo rotulo="Descrição"><textarea value={f.descricao || ""} onChange={set("descricao")} /></Campo>
      <h3 style={{ marginTop: 10 }}>Dados técnicos de referência</h3>
      <div className="grade g4">
        {DADOS.map(([k, r]) => <Campo key={k} rotulo={r}><input value={f.dados[k]} onChange={setD(k)} /></Campo>)}
        <Campo rotulo="Exaustor (código/modelo)"><input value={f.dados.exaustor} onChange={setD("exaustor")} /></Campo>
        <Campo rotulo="Diâmetros usados (mm)" dica="separados por ponto e vírgula"><input value={f.dados.diametros_mm} onChange={setD("diametros_mm")} /></Campo>
      </div>
      <div className="grade g2" style={{ marginTop: 8 }}>
        <Campo rotulo="Desempenho real observado"><textarea value={f.desempenho_real || ""} onChange={set("desempenho_real")} /></Campo>
        <Campo rotulo="Confiabilidade dos dados">
          <select value={f.confiabilidade || "nao_verificado"} onChange={set("confiabilidade")}>{Object.entries(CONF).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </Campo>
      </div>
      <ErroBox erro={erro} />
      <div className="acoes" style={{ marginTop: 8 }}><BotaoAcao className="btn btn-primario" onClick={salvar}>Salvar</BotaoAcao><button className="btn" onClick={aoCancelar}>Cancelar</button></div>
    </Cartao>
  );
}

function Detalhe({ a, projetos, aoAtualizar }: { a: any; projetos: any[]; aoAtualizar: () => void }) {
  const { pode } = useAuth();
  const [pid, setPid] = useState("");
  const [tol, setTol] = useState("10");
  const [cmp, setCmp] = useState<any>(null);
  const [erro, setErro] = useState<unknown>(null);
  useEffect(() => { setCmp(null); }, [a.id]);
  return (
    <>
      <Cartao titulo={`Anexos — ${a.nome}`}>
        {pode("antigos.editar") && (
          <input type="file" multiple onChange={async (e) => {
            for (const f of Array.from(e.target.files || [])) {
              const fd = new FormData();
              fd.append("arquivo", f);
              fd.append("projeto_antigo_id", String(a.id));
              fd.append("categoria", /\.(dxf|dwg)$/i.test(f.name) ? "desenho" : /\.pdf$/i.test(f.name) ? "documento" : /\.(xlsx|csv)$/i.test(f.name) ? "tabela" : "documento");
              try { await api.enviar("/arquivos", fd); } catch (er) { setErro(er); }
            }
            e.target.value = "";
            aoAtualizar();
          }} />
        )}
        <p className="nota">Desenhos DWG/DXF, plantas PDF, memoriais, tabelas de equipamentos, listas de materiais, fotos da instalação executada.</p>
        <table>
          <tbody>{a.arquivos.map((f: any) => (
            <tr key={f.id}><td>{f.nome}</td><td>{f.categoria}</td><td>{dataHora(f.criado_em)}</td>
              <td><button className="btn btn-mini" onClick={() => api.baixar(`/arquivos/${f.id}/download`, f.nome)}>Baixar</button></td></tr>
          ))}</tbody>
        </table>
      </Cartao>
      <Cartao titulo="Comparar com projeto gerado pelo software">
        <div className="form-linha">
          <Campo rotulo="Projeto">
            <select value={pid} onChange={(e) => setPid(e.target.value)} style={{ minWidth: 280 }}>
              <option value="">— selecione —</option>
              {projetos.map((p) => <option key={p.id} value={p.id}>{p.codigo} — {p.nome}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Tolerância (%)"><input value={tol} onChange={(e) => setTol(e.target.value)} style={{ width: 80 }} /></Campo>
          <BotaoAcao className="btn btn-primario" disabled={!pid} onClick={async () => {
            setErro(null);
            try { setCmp(await api.get(`/antigos/${a.id}/comparar/${pid}?tolerancia_pct=${numero(tol) ?? 10}`)); } catch (e) { setErro(e); }
          }}>Comparar</BotaoAcao>
        </div>
        <ErroBox erro={erro} />
        {cmp && (
          <div style={{ marginTop: 10 }}>
            <p className="nota">Projeto antigo “{cmp.projeto_antigo}” × {cmp.projeto} (cálculo nº {cmp.calculo_id}) — tolerância {fmt(cmp.tolerancia_pct)}%</p>
            <table>
              <thead><tr><th>Grandeza</th><th className="num">Projeto antigo</th><th className="num">Gerado</th><th className="num">Diferença</th><th>Situação</th></tr></thead>
              <tbody>{Object.entries(cmp.grandezas).map(([k, v]: [string, any]) => (
                <tr key={k}><td>{NOMES_GRANDEZA[k] || k}</td><td className="num">{fmt(v.referencia, Number.isInteger(v.referencia) ? 0 : 1)}</td><td className="num">{fmt(v.gerado, Number.isInteger(v.gerado) ? 0 : 1)}</td>
                  <td className="num">{v.diferenca_pct != null ? `${v.diferenca_pct > 0 ? "+" : ""}${fmt(v.diferenca_pct, 1)}%` : "—"}</td>
                  <td>{v.situacao === "ok" ? <span className="div-ok">dentro da tolerância</span> : v.situacao === "divergente" ? <span className="div-erro">divergente</span> : <span className="nota">sem dado</span>}</td></tr>
              ))}
                <tr><td>Exaustor</td><td className="num">{cmp.exaustor.referencia || "—"}</td><td className="num">{cmp.exaustor.gerado || "—"}</td><td></td>
                  <td>{cmp.exaustor.situacao === "ok" ? <span className="div-ok">igual</span> : cmp.exaustor.situacao === "divergente" ? <span className="div-erro">diferente</span> : <span className="nota">sem dado</span>}</td></tr>
                <tr><td>Diâmetros (mm)</td><td className="num">{cmp.diametros.referencia.join(", ") || "—"}</td><td className="num">{cmp.diametros.gerado.join(", ") || "—"}</td><td></td>
                  <td>{cmp.diametros.somente_referencia.length || cmp.diametros.somente_gerado.length ? <span className="div-erro">só no antigo: {cmp.diametros.somente_referencia.join(", ") || "—"} · só no gerado: {cmp.diametros.somente_gerado.join(", ") || "—"}</span> : <span className="div-ok">iguais</span>}</td></tr>
              </tbody>
            </table>
            <p className="nota">Trajetos: {cmp.trajetos.observacao}</p>
            {cmp.observacoes.map((o: string, i: number) => <Alerta key={i} tipo="aviso">{o}</Alerta>)}
          </div>
        )}
      </Cartao>
    </>
  );
}

export default function Antigos() {
  const { pode } = useAuth();
  const { dados, erro, recarregar } = useCarregar(() => Promise.all([api.get<any[]>("/antigos"), api.get<any[]>("/projetos")]));
  const [form, setForm] = useState<any>(null);
  const [sel, setSel] = useState<number | null>(null);
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  const [antigos, projetos] = dados;
  const atual = antigos.find((a) => a.id === sel);
  return (
    <div>
      <div className="cabecalho">
        <div><h1>Biblioteca de projetos anteriores</h1><div className="sub">Referência e validação — projetos antigos não são considerados automaticamente corretos</div></div>
        {pode("antigos.editar") && <button className="btn btn-primario" onClick={() => setForm({ confiabilidade: "nao_verificado" })}>Adicionar projeto anterior</button>}
      </div>
      {form && <Form inicial={form} aoCancelar={() => setForm(null)} aoSalvar={() => { setForm(null); recarregar(); }} />}
      <Cartao>
        <table>
          <thead><tr><th>Nome</th><th>Cliente</th><th>Ano</th><th>Sistema</th><th className="num">Vazão (m³/h)</th><th>Confiabilidade</th><th className="num">Anexos</th><th></th></tr></thead>
          <tbody>{antigos.map((a) => (
            <tr key={a.id} className={a.id === sel ? "clicavel selecionada" : "clicavel"} onClick={() => setSel(a.id)}>
              <td>{a.nome}</td><td>{a.cliente}</td><td>{a.ano}</td><td>{MODULOS[a.modulo] || "—"}</td><td className="num">{fmt(a.dados?.vazao_total_m3h)}</td>
              <td><Selo tipo={a.confiabilidade === "nao_verificado" ? "aviso" : "ok"}>{a.confiabilidade_nome}</Selo></td><td className="num">{a.arquivos.length}</td>
              <td>{pode("antigos.editar") && <button className="btn btn-mini" onClick={(e) => { e.stopPropagation(); setForm(a); }}>Editar</button>}</td>
            </tr>
          ))}</tbody>
        </table>
        {!antigos.length && <div className="vazio">Nenhum projeto anterior. Importe quando quiser — não é obrigatório.</div>}
      </Cartao>
      {atual && <Detalhe a={atual} projetos={projetos} aoAtualizar={recarregar} />}
    </div>
  );
}
