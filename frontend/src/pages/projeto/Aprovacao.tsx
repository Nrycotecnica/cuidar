import { useEffect, useState } from "react";
import { Alerta, BotaoAcao, Carregando, Cartao, ErroBox, SeloStatus } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dataHora } from "../../lib/format";
import type { CtxProjeto } from "./Projeto";

export default function Aprovacao({ ctx }: { ctx: CtxProjeto }) {
  const { pode } = useAuth();
  const p = ctx.projeto;
  const [pend, setPend] = useState<any>(null);
  const [erro, setErro] = useState<unknown>(null);
  const carregar = () => api.get(`/projetos/${p.id}/pendencias`).then(setPend).catch(setErro);
  useEffect(() => { carregar(); /* eslint-disable-next-line */ }, [p.id, p.status, ctx.calculos.length]);
  const acao = (a: string, extra: any = {}) => async () => {
    setErro(null);
    try {
      await api.post(`/projetos/${p.id}/status`, { acao: a, ...extra });
      await ctx.recarregar();
      await carregar();
    } catch (e) { setErro(e); }
  };
  if (!pend) return <Carregando />;
  return (
    <div>
      <Cartao titulo="Situação">
        <p>Situação atual: <SeloStatus status={p.status} /> · revisão {p.versao}{p.aprovado_em && ` · aprovado em ${dataHora(p.aprovado_em)}`}{p.calculo_aprovado_id && ` · cálculo aprovado nº ${p.calculo_aprovado_id}`}</p>
        <div className="acoes">
          {p.status === "rascunho" && pode("projetos.editar") && <BotaoAcao className="btn" onClick={acao("enviar_revisao")}>Enviar para revisão técnica</BotaoAcao>}
          {p.status === "em_revisao" && pode("projetos.aprovar") && (
            <BotaoAcao className="btn btn-ok" onClick={acao("aprovar", { calculo_id: ctx.calcId || undefined })} confirmar={`Aprovar tecnicamente o projeto com o cálculo nº ${ctx.calcId}? Esta ação será registrada com seu nome.`}>
              Aprovar (cálculo nº {ctx.calcId ?? "—"})
            </BotaoAcao>
          )}
          {p.status === "aprovado" && pode("fabricacao.liberar") && <BotaoAcao className="btn btn-ok" onClick={acao("liberar_fabricacao")} confirmar="Liberar o projeto para fabricação?">Liberar para fabricação</BotaoAcao>}
          {p.status !== "rascunho" && pode("projetos.editar") && (
            <BotaoAcao className="btn btn-perigo" onClick={acao("voltar_rascunho")} confirmar={["aprovado", "liberado_fabricacao"].includes(p.status) ? "Reabrir o projeto aprovado? Será criada uma nova revisão e a aprovação será removida." : undefined}>
              Voltar para rascunho
            </BotaoAcao>
          )}
        </div>
        <ErroBox erro={erro} />
      </Cartao>
      <Cartao titulo={`Pendências para aprovação técnica (cálculo nº ${pend.calculo_id ?? "—"})`}>
        {pend.pendencias.length ? (
          <ul>{pend.pendencias.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
        ) : <Alerta tipo="ok">Nenhuma pendência: o projeto pode ser aprovado pelo engenheiro responsável.</Alerta>}
        <p className="nota">A aprovação exige: cálculo sem bloqueios, dados de entrada confirmados, parâmetros técnicos e equipamento aprovados no catálogo, verificações de segurança concluídas e projeto não demonstrativo. Nem a IA nem perfis sem permissão podem aprovar.</p>
      </Cartao>
    </div>
  );
}
