import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dataHora, MODULOS, numero, RISCOS, TIPOS_CAPTOR } from "../lib/format";
import { useCarregar } from "../lib/hooks";

const NUM_TOPO = ["comprimento_m", "largura_m", "pe_direito_m", "temperatura_c", "altitude_m", "ocupantes"];
const NUM_PONTO = ["x", "y", "distancia_m", "area_face_m2", "vazao_m3h"];
const NUM_RET = ["x", "y", "largura", "profundidade"];

function retPontos(r: any) {
  const x = numero(r.x), y = numero(r.y), w = numero(r.largura), d = numero(r.profundidade);
  if (x === null || y === null || !w || !d) return undefined;
  return [[x, y], [x + w, y], [x + w, y + d], [x, y + d]];
}

/** Converte o formulário (strings) em dados da visita (números). */
export function paraDados(f: any) {
  const d: any = { ...f };
  for (const k of NUM_TOPO) d[k] = numero(f[k]);
  d.pontos_emissao = (f.pontos_emissao || []).map((p: any) => {
    const o: any = { ...p };
    for (const k of NUM_PONTO) o[k] = numero(p[k]);
    return o;
  });
  d.maquinas = (f.maquinas || []).map((m: any) => {
    const o: any = { ...m };
    for (const k of NUM_RET) o[k] = numero(m[k]);
    o.pontos = retPontos(m);
    return o;
  });
  d.pilares = (f.pilares || []).map((m: any) => {
    const o: any = { ...m };
    for (const k of NUM_RET) o[k] = numero(m[k]);
    o.pontos = retPontos(m);
    return o;
  });
  if (!d.pilares_obstaculos && (d.pilares.length || d.maquinas.length)) d.pilares_obstaculos = "ver listas";
  return d;
}

function paraForm(d: any) {
  const f: any = { ...d };
  for (const k of NUM_TOPO) f[k] = d[k] ?? "";
  f.pontos_emissao = d.pontos_emissao || [];
  f.maquinas = d.maquinas || [];
  f.pilares = d.pilares || [];
  f.riscos = d.riscos || {};
  return f;
}

function Lista({ titulo, itens, campos, novo, onChange }: { titulo: string; itens: any[]; campos: [string, string, string?][]; novo: any; onChange: (l: any[]) => void }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div className="cartao-cab"><h3>{titulo}</h3><button className="btn btn-mini" onClick={() => onChange([...itens, { ...novo }])}>+ Adicionar</button></div>
      {itens.map((it, i) => (
        <div className="linha-item" key={i} style={{ gridTemplateColumns: `repeat(${campos.length}, minmax(80px, 1fr)) auto` }}>
          {campos.map(([k, rot, tipo]) => (
            <Campo key={k} rotulo={rot}>
              {tipo === "captor" ? (
                <select value={it[k] || ""} onChange={(e) => onChange(itens.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)))}>
                  <option value="">—</option>
                  {Object.entries(TIPOS_CAPTOR).map(([a, b]) => <option key={a} value={a}>{b}</option>)}
                </select>
              ) : tipo === "processo" ? (
                <select value={it[k] || ""} onChange={(e) => onChange(itens.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)))}>
                  <option value="">—</option>
                  <option value="baixa_dispersao">Baixa dispersão</option>
                  <option value="media_dispersao">Média dispersão</option>
                  <option value="alta_dispersao">Alta dispersão</option>
                  <option value="solda">Solda</option>
                </select>
              ) : (
                <input value={it[k] ?? ""} onChange={(e) => onChange(itens.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)))} />
              )}
            </Campo>
          ))}
          <button className="btn btn-mini btn-perigo" onClick={() => onChange(itens.filter((_, j) => j !== i))}>Remover</button>
        </div>
      ))}
      {!itens.length && <div className="nota">Nenhum item.</div>}
    </div>
  );
}

function FormVisita({ visita, clientes, aoSalvar }: { visita: any; clientes: any[]; aoSalvar: (v: any) => void }) {
  const { pode } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [cab, setCab] = useState({ cliente_id: visita.cliente_id ?? "", data: visita.data || new Date().toISOString().slice(0, 10), responsavel_visita: visita.responsavel_visita || "" });
  const [f, setF] = useState<any>(paraForm(visita.dados || {}));
  const [erro, setErro] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>((loc.state as any)?.salvo ? "Visita salva." : null);
  const [arquivos, setArquivos] = useState<any[]>([]);
  const [faltantes, setFaltantes] = useState<string[]>(visita.faltantes || []);
  useEffect(() => {
    if (visita.id) api.get<any[]>(`/arquivos?visita_id=${visita.id}`).then(setArquivos).catch(() => {});
  }, [visita.id]);
  const cli = clientes.find((c) => String(c.id) === String(cab.cliente_id));
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const salvar = async () => {
    setErro(null);
    try {
      const corpo = { ...cab, cliente_id: cab.cliente_id ? Number(cab.cliente_id) : null, dados: paraDados(f) };
      const v = visita.id ? await api.put(`/visitas/${visita.id}`, corpo) : await api.post("/visitas", corpo);
      setFaltantes(v.faltantes);
      setMsg("Visita salva.");
      aoSalvar(v);
      return v;
    } catch (e) {
      setErro(e);
    }
  };
  return (
    <div>
      <Cartao titulo={visita.id ? `Visita técnica nº ${visita.id}` : "Nova visita técnica"}>
        <div className="grade g3">
          <Campo rotulo="Cliente">
            <select value={cab.cliente_id} onChange={(e) => setCab({ ...cab, cliente_id: e.target.value })}>
              <option value="">— selecione —</option>
              {clientes.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Data da visita"><input type="date" value={cab.data} onChange={(e) => setCab({ ...cab, data: e.target.value })} /></Campo>
          <Campo rotulo="Responsável pela visita"><input value={cab.responsavel_visita} onChange={(e) => setCab({ ...cab, responsavel_visita: e.target.value })} /></Campo>
        </div>
        {cli && <p className="nota">Endereço: {cli.endereco || "não cadastrado"} · Contato: {cli.contato_nome || "—"} {cli.contato_telefone || ""}</p>}
        <div className="grade g3" style={{ marginTop: 8 }}>
          <Campo rotulo="Tipo de atividade industrial"><input value={f.atividade || ""} onChange={set("atividade")} /></Campo>
          <Campo rotulo="Tipo de sistema necessário">
            <select value={f.tipo_sistema || ""} onChange={set("tipo_sistema")}>
              <option value="">— a definir —</option>
              {Object.entries(MODULOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Contaminantes / materiais envolvidos"><input value={f.contaminantes || ""} onChange={set("contaminantes")} /></Campo>
        </div>
        <Campo rotulo="Descrição do problema"><textarea value={f.descricao_problema || ""} onChange={set("descricao_problema")} /></Campo>
        <h2>Ambiente e condições operacionais</h2>
        <div className="grade g3">
          <Campo rotulo="Comprimento (m)"><input inputMode="decimal" value={f.comprimento_m} onChange={set("comprimento_m")} /></Campo>
          <Campo rotulo="Largura (m)"><input inputMode="decimal" value={f.largura_m} onChange={set("largura_m")} /></Campo>
          <Campo rotulo="Pé-direito (m)"><input inputMode="decimal" value={f.pe_direito_m} onChange={set("pe_direito_m")} /></Campo>
          <Campo rotulo="Temperatura de operação (°C)"><input inputMode="decimal" value={f.temperatura_c} onChange={set("temperatura_c")} /></Campo>
          <Campo rotulo="Altitude do local (m)"><input inputMode="decimal" value={f.altitude_m} onChange={set("altitude_m")} /></Campo>
          <Campo rotulo="Ocupantes"><input inputMode="numeric" value={f.ocupantes} onChange={set("ocupantes")} /></Campo>
        </div>
        <Campo rotulo="Condições operacionais (turnos, processos, umidade…)"><textarea value={f.condicoes_operacionais || ""} onChange={set("condicoes_operacionais")} /></Campo>
        <p className="nota">Coordenadas em metros a partir de um canto de referência do ambiente (x ao longo do comprimento, y ao longo da largura).</p>
        <Lista titulo="Pontos de emissão" itens={f.pontos_emissao} onChange={(l) => setF({ ...f, pontos_emissao: l })} novo={{ nome: "", x: "", y: "" }}
          campos={[["nome", "Nome"], ["x", "X (m)"], ["y", "Y (m)"], ["tipo", "Tipo de captor", "captor"], ["processo", "Dispersão/processo", "processo"], ["distancia_m", "Distância X (m)"], ["area_face_m2", "Área de face (m²)"], ["vazao_m3h", "Vazão informada (m³/h)"]]} />
        <Lista titulo="Máquinas instaladas" itens={f.maquinas} onChange={(l) => setF({ ...f, maquinas: l })} novo={{ nome: "" }}
          campos={[["nome", "Nome"], ["x", "X (m)"], ["y", "Y (m)"], ["largura", "Largura (m)"], ["profundidade", "Profundidade (m)"]]} />
        <Lista titulo="Pilares" itens={f.pilares} onChange={(l) => setF({ ...f, pilares: l })} novo={{ largura: "0,4", profundidade: "0,4" }}
          campos={[["x", "X (m)"], ["y", "Y (m)"], ["largura", "Largura (m)"], ["profundidade", "Profundidade (m)"]]} />
        <Campo rotulo="Pilares e obstáculos (descrição)"><textarea value={f.pilares_obstaculos || ""} onChange={set("pilares_obstaculos")} /></Campo>
        <h2>Riscos</h2>
        <div className="grade g2">
          {Object.entries(RISCOS).map(([k, v]) => (
            <label key={k}><input type="checkbox" checked={!!f.riscos[k]} onChange={(e) => setF({ ...f, riscos: { ...f.riscos, [k]: e.target.checked } })} /> {v}</label>
          ))}
        </div>
        <Campo rotulo="Observações"><textarea value={f.observacoes || ""} onChange={set("observacoes")} /></Campo>
        <ErroBox erro={erro} />
        {msg && <Alerta tipo="ok">{msg}</Alerta>}
        <div className="acoes" style={{ marginTop: 10 }}>
          {pode("visitas.editar") && <BotaoAcao className="btn btn-primario" onClick={salvar}>Salvar visita</BotaoAcao>}
          {visita.id && pode("projetos.editar") && (
            <BotaoAcao className="btn" onClick={async () => {
              const v = await salvar();
              if (!v) return;
              try {
                const p = await api.post(`/visitas/${visita.id}/criar-projeto`, {});
                nav(`/projetos/${p.id}`);
              } catch (e) { setErro(e); }
            }}>Criar projeto a partir da visita</BotaoAcao>
          )}
        </div>
      </Cartao>
      <Cartao titulo="Dados técnicos ainda a levantar">
        {faltantes.length ? <ul>{faltantes.map((x, i) => <li key={i}>{x}</li>)}</ul> : <Alerta tipo="ok">Nenhum dado essencial pendente segundo as regras de verificação.</Alerta>}
        <p className="nota">O projeto pode ser criado com dados parciais; valores da visita entram como "não confirmados" e bloqueiam a aprovação técnica até serem confirmados.</p>
      </Cartao>
      {visita.id && (
        <Cartao titulo="Fotos, vídeos e documentos">
          {pode("visitas.editar") && (
            <input type="file" multiple onChange={async (e) => {
              const fs = Array.from(e.target.files || []);
              for (const arq of fs) {
                const fd = new FormData();
                fd.append("arquivo", arq);
                fd.append("visita_id", String(visita.id));
                fd.append("categoria", arq.type.startsWith("image/") ? "foto" : arq.type.startsWith("video/") ? "video" : "documento");
                try { await api.enviar("/arquivos", fd); } catch (er) { setErro(er); }
              }
              e.target.value = "";
              setArquivos(await api.get(`/arquivos?visita_id=${visita.id}`));
            }} />
          )}
          <table style={{ marginTop: 8 }}>
            <thead><tr><th>Arquivo</th><th>Categoria</th><th className="num">Tamanho</th><th>Enviado</th><th></th></tr></thead>
            <tbody>
              {arquivos.map((a) => (
                <tr key={a.id}><td>{a.nome}</td><td>{a.categoria}</td><td className="num">{(a.tamanho / 1024).toFixed(0)} kB</td><td>{dataHora(a.criado_em)}</td>
                  <td><button className="btn btn-mini" onClick={() => api.baixar(`/arquivos/${a.id}/download`, a.nome)}>Baixar</button></td></tr>
              ))}
            </tbody>
          </table>
        </Cartao>
      )}
    </div>
  );
}

export default function Visitas() {
  const { pode } = useAuth();
  const { id } = useParams();
  const nav = useNavigate();
  const { dados, erro, recarregar } = useCarregar(() => Promise.all([api.get<any[]>("/visitas"), api.get<any[]>("/clientes")]));
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  const [visitas, clientes] = dados;
  if (id) {
    const v = id === "nova" ? { dados: {} } : visitas.find((x) => String(x.id) === id);
    if (!v) return <Alerta tipo="erro">Visita não encontrada.</Alerta>;
    return (
      <div>
        <div className="cabecalho"><h1>Visita técnica</h1><button className="btn" onClick={() => nav("/visitas")}>← Voltar</button></div>
        <FormVisita key={id} visita={v} clientes={clientes} aoSalvar={(nv) => { recarregar(); if (id === "nova") nav(`/visitas/${nv.id}`, { replace: true, state: { salvo: true } }); }} />
      </div>
    );
  }
  const nomeCli = (cid: number) => clientes.find((c) => c.id === cid)?.nome || "—";
  return (
    <div>
      <div className="cabecalho">
        <div><h1>Visitas técnicas</h1><div className="sub">Registro digital das visitas aos clientes</div></div>
        {pode("visitas.editar") && <button className="btn btn-primario" onClick={() => nav("/visitas/nova")}>Nova visita</button>}
      </div>
      <Cartao>
        <table>
          <thead><tr><th>Nº</th><th>Data</th><th>Cliente</th><th>Atividade</th><th>Sistema</th><th className="num">Pendências</th><th>Projeto</th></tr></thead>
          <tbody>
            {visitas.map((v) => (
              <tr key={v.id} className="clicavel" onClick={() => nav(`/visitas/${v.id}`)}>
                <td>{v.id}</td><td>{v.data}</td><td>{nomeCli(v.cliente_id)}</td><td>{v.dados?.atividade}</td>
                <td>{MODULOS[v.dados?.tipo_sistema] || "—"}</td><td className="num">{v.faltantes.length}</td>
                <td>{v.projeto_id ? `#${v.projeto_id}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!visitas.length && <div className="vazio">Nenhuma visita registrada.</div>}
      </Cartao>
    </div>
  );
}
