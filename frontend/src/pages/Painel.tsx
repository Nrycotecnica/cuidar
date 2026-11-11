import { Link } from "react-router-dom";
import { Alerta, Carregando, Cartao, SeloDemo, SeloStatus } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dataHora, MODULOS, STATUS_PROJETO } from "../lib/format";
import { useCarregar } from "../lib/hooks";

export default function Painel() {
  const { usuario, pode } = useAuth();
  const { dados, erro } = useCarregar(() => api.get("/painel"));
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  const c = dados.projetos_por_status || {};
  return (
    <div>
      <div className="cabecalho">
        <div>
          <h1>Olá, {usuario?.nome}</h1>
          <div className="sub">Painel de projetos de exaustão e ventilação industrial</div>
        </div>
        <div className="acoes">
          {pode("visitas.editar") && <Link className="btn" to="/visitas">Nova visita técnica</Link>}
          {pode("projetos.editar") && <Link className="btn btn-primario" to="/projetos?novo=1">Novo projeto</Link>}
        </div>
      </div>
      <div className="indicadores">
        {Object.entries(STATUS_PROJETO).map(([k, r]) => (
          <div className="indicador" key={k}><div className="v">{c[k] || 0}</div><div className="r">{r}</div></div>
        ))}
        <div className="indicador"><div className="v">{dados.total_clientes}</div><div className="r">Clientes</div></div>
        <div className="indicador"><div className="v">{dados.total_calculos}</div><div className="r">Cálculos executados</div></div>
      </div>
      <Cartao titulo="Projetos recentes" acoes={<Link to="/projetos">Ver todos</Link>}>
        <table>
          <thead><tr><th>Código</th><th>Projeto</th><th>Sistema</th><th>Situação</th><th>Atualizado</th></tr></thead>
          <tbody>
            {dados.recentes.map((p: any) => (
              <tr key={p.id}>
                <td><Link to={`/projetos/${p.id}`}>{p.codigo}</Link></td>
                <td>{p.nome} <SeloDemo ativo={p.demonstrativo} /></td>
                <td>{MODULOS[p.modulo]}</td>
                <td><SeloStatus status={p.status} /></td>
                <td>{dataHora(p.atualizado_em)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Cartao>
      <Alerta tipo="info">
        Os cálculos são feitos por algoritmos de engenharia verificáveis. Resultados permanecem <strong>preliminares</strong> até a aprovação
        de um engenheiro responsável; dados demonstrativos são fictícios e não podem ser usados em instalações.
      </Alerta>
    </div>
  );
}
