import { useEffect, useState } from "react";
import { Alerta, BotaoAcao, Carregando, Cartao, ErroBox, Vazio } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmt } from "../../lib/format";
import { SeletorCalculo } from "./Calculo";
import type { CtxProjeto } from "./Projeto";

export default function Documentos({ ctx }: { ctx: CtxProjeto }) {
  const { pode } = useAuth();
  const [lista, setLista] = useState<any>(null);
  const [erro, setErro] = useState<unknown>(null);
  const calc = ctx.calculos.find((c) => c.id === ctx.calcId);
  useEffect(() => {
    setLista(null);
    setErro(null);
    if (calc?.tipo === "rede") api.get(`/calculos/${calc.id}/lista`).then(setLista).catch(setErro);
  }, [calc?.id]);
  if (!ctx.calculos.length) return <Vazio>Execute um cálculo para gerar desenhos, memorial e listas.</Vazio>;
  const cid = ctx.calcId;
  const baixar = (sufixo: string, nome: string) => async () => {
    try { await api.baixar(`/calculos/${cid}/${sufixo}`, nome); } catch (e) { setErro(e); }
  };
  const aprovado = ctx.projeto.calculo_aprovado_id === cid && ["aprovado", "liberado_fabricacao"].includes(ctx.projeto.status);
  return (
    <div>
      <div className="form-linha" style={{ marginBottom: 10 }}><SeletorCalculo ctx={ctx} /></div>
      {!aprovado && <Alerta tipo="aviso">Documentos deste cálculo serão emitidos como <strong>PRELIMINARES — NÃO APROVADOS PARA EXECUÇÃO</strong>.</Alerta>}
      <Cartao titulo="Exportações">
        {!pode("exportar") ? <p className="nota">Seu perfil não permite exportar.</p> : (
          <div className="acoes">
            {calc?.tipo === "rede" && <BotaoAcao className="btn btn-primario" onClick={baixar("dxf", "desenho.dxf")}>Desenho DXF (editável)</BotaoAcao>}
            <BotaoAcao className="btn" onClick={baixar("desenho.pdf", "desenho.pdf")}>Desenho PDF</BotaoAcao>
            <BotaoAcao className="btn" onClick={baixar("memorial.pdf", "memorial.pdf")}>Memorial de cálculo (PDF)</BotaoAcao>
            {calc?.tipo === "rede" && <>
              <BotaoAcao className="btn" onClick={baixar("lista.xlsx", "lista.xlsx")}>Lista de materiais (Excel)</BotaoAcao>
              <BotaoAcao className="btn" onClick={baixar("lista.csv", "lista.csv")}>Lista (CSV)</BotaoAcao>
              <BotaoAcao className="btn" onClick={baixar("lista.pdf", "lista.pdf")}>Lista (PDF)</BotaoAcao>
            </>}
          </div>
        )}
        <p className="nota">O DXF usa milímetros, escala 1:1, camadas VENT-*/ARQ-*, blocos com atributos e cotas — abre no AutoCAD e em softwares CAD compatíveis.</p>
        <ErroBox erro={erro} />
      </Cartao>
      {calc?.tipo === "rede" && (lista ? (
        <Cartao titulo="Lista de materiais">
          <Alerta tipo={lista.liberado ? "ok" : "aviso"}><strong>{lista.situacao}</strong></Alerta>
          <div className="tabela-rolagem">
            <table>
              <thead><tr><th>Item</th><th>Categoria</th><th>Código</th><th>Descrição</th><th className="num">Qtd</th><th>Un</th><th className="num">Custo unit.</th><th className="num">Custo total</th><th>Obs.</th></tr></thead>
              <tbody>{lista.itens.map((i: any) => (
                <tr key={i.item}><td>{i.item}</td><td>{i.categoria}</td><td><code>{i.codigo}</code></td><td>{i.descricao}</td><td className="num">{fmt(i.quantidade, Number.isInteger(i.quantidade) ? 0 : 2)}</td>
                  <td>{i.unidade}</td><td className="num">{i.custo_unitario != null ? fmt(i.custo_unitario, 2) : "—"}</td><td className="num">{i.custo_total != null ? fmt(i.custo_total, 2) : "—"}</td><td className="nota">{i.observacao}</td></tr>
              ))}</tbody>
            </table>
          </div>
          {lista.total_custo != null && <p><strong>Total (itens com custo cadastrado): R$ {fmt(lista.total_custo, 2)}</strong> · {lista.itens_sem_custo} item(ns) sem custo</p>}
          <ul className="nota">{lista.regras.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
          {lista.avisos?.length > 0 && <Alerta tipo="aviso">{lista.avisos.join(" · ")}</Alerta>}
        </Cartao>
      ) : !erro && <Carregando />)}
    </div>
  );
}
