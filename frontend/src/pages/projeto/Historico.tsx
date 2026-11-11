import { Carregando, Cartao } from "../../components/ui";
import { api } from "../../lib/api";
import { dataHora } from "../../lib/format";
import { useCarregar } from "../../lib/hooks";
import type { CtxProjeto } from "./Projeto";

export default function Historico({ ctx }: { ctx: CtxProjeto }) {
  const { dados } = useCarregar(() => api.get<any[]>(`/projetos/${ctx.projeto.id}/historico`), [ctx.projeto.id]);
  if (!dados) return <Carregando />;
  return (
    <Cartao titulo="Histórico de edições, cálculos e aprovações">
      <div className="tabela-rolagem">
        <table>
          <thead><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr></thead>
          <tbody>
            {dados.map((a) => (
              <tr key={a.id}><td>{dataHora(a.criado_em)}</td><td>{a.usuario_nome}</td><td>{a.acao}</td>
                <td><code style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{a.detalhes ? JSON.stringify(a.detalhes) : ""}</code></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </Cartao>
  );
}
