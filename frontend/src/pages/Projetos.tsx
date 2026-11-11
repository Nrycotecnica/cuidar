import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox, SeloDemo, SeloStatus } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dataHora, MODULOS, STATUS_PROJETO } from "../lib/format";
import { useCarregar } from "../lib/hooks";

export default function Projetos() {
  const { pode } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const { dados, erro } = useCarregar(() => Promise.all([api.get<any[]>("/projetos"), api.get<any[]>("/clientes")]));
  const [novo, setNovo] = useState<any | null>(sp.get("novo") ? { nome: "", modulo: "poeira", cliente_id: "", descricao: "" } : null);
  const [erroNovo, setErroNovo] = useState<unknown>(null);
  const [fStatus, setFStatus] = useState("");
  const [fModulo, setFModulo] = useState("");
  const [busca, setBusca] = useState("");
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  const [projetos, clientes] = dados;
  const lista = projetos.filter((p) => (!fStatus || p.status === fStatus) && (!fModulo || p.modulo === fModulo) &&
    `${p.codigo} ${p.nome} ${p.cliente_nome || ""}`.toLowerCase().includes(busca.toLowerCase()));
  return (
    <div>
      <div className="cabecalho">
        <div><h1>Projetos</h1><div className="sub">{projetos.length} projeto(s)</div></div>
        <div className="acoes">
          <input placeholder="Buscar…" value={busca} onChange={(e) => setBusca(e.target.value)} style={{ width: 180 }} />
          <select value={fStatus} onChange={(e) => setFStatus(e.target.value)} style={{ width: 190 }}>
            <option value="">Todas as situações</option>
            {Object.entries(STATUS_PROJETO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={fModulo} onChange={(e) => setFModulo(e.target.value)} style={{ width: 200 }}>
            <option value="">Todos os sistemas</option>
            {Object.entries(MODULOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          {pode("projetos.editar") && <button className="btn btn-primario" onClick={() => setNovo({ nome: "", modulo: "poeira", cliente_id: "", descricao: "" })}>Novo projeto</button>}
        </div>
      </div>
      {novo && (
        <Cartao titulo="Novo projeto">
          <div className="grade g3">
            <Campo rotulo="Nome do projeto *"><input value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} /></Campo>
            <Campo rotulo="Tipo de sistema *">
              <select value={novo.modulo} onChange={(e) => setNovo({ ...novo, modulo: e.target.value })}>
                {Object.entries(MODULOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Campo>
            <Campo rotulo="Cliente">
              <select value={novo.cliente_id} onChange={(e) => setNovo({ ...novo, cliente_id: e.target.value })}>
                <option value="">— sem cliente —</option>
                {clientes.map((c: any) => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </select>
            </Campo>
          </div>
          <Campo rotulo="Descrição"><textarea value={novo.descricao} onChange={(e) => setNovo({ ...novo, descricao: e.target.value })} /></Campo>
          <ErroBox erro={erroNovo} />
          <div className="acoes" style={{ marginTop: 10 }}>
            <BotaoAcao className="btn btn-primario" onClick={async () => {
              try {
                const p = await api.post("/projetos", { ...novo, cliente_id: novo.cliente_id ? Number(novo.cliente_id) : null });
                nav(`/projetos/${p.id}`);
              } catch (e) { setErroNovo(e); }
            }}>Criar projeto</BotaoAcao>
            <button className="btn" onClick={() => setNovo(null)}>Cancelar</button>
          </div>
        </Cartao>
      )}
      <Cartao>
        <table>
          <thead><tr><th>Código</th><th>Projeto</th><th>Cliente</th><th>Sistema</th><th>Situação</th><th className="num">Rev.</th><th>Atualizado</th></tr></thead>
          <tbody>
            {lista.map((p) => (
              <tr key={p.id} className="clicavel" onClick={() => nav(`/projetos/${p.id}`)}>
                <td><Link to={`/projetos/${p.id}`}>{p.codigo}</Link></td>
                <td>{p.nome} <SeloDemo ativo={p.demonstrativo} /></td>
                <td>{p.cliente_nome}</td>
                <td>{p.modulo_nome}</td>
                <td><SeloStatus status={p.status} /></td>
                <td className="num">{p.versao}</td>
                <td>{dataHora(p.atualizado_em)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!lista.length && <div className="vazio">Nenhum projeto encontrado.</div>}
      </Cartao>
    </div>
  );
}
