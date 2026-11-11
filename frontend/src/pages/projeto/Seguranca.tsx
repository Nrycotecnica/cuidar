import { useEffect, useState } from "react";
import { Alerta, Carregando, Cartao, ErroBox, Selo } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dataHora } from "../../lib/format";
import type { CtxProjeto } from "./Projeto";

export default function Seguranca({ ctx }: { ctx: CtxProjeto }) {
  const { pode } = useAuth();
  const p = ctx.projeto;
  const editavel = pode("projetos.editar") && !["aprovado", "liberado_fabricacao"].includes(p.status);
  const engenheiro = pode("projetos.aprovar") && editavel;
  const [d, setD] = useState<any>(null);
  const [erro, setErro] = useState<unknown>(null);
  useEffect(() => { api.get(`/projetos/${p.id}/seguranca`).then(setD).catch(setErro); }, [p.id]);
  const enviar = async (corpo: any) => {
    setErro(null);
    try { setD(await api.put(`/projetos/${p.id}/seguranca`, corpo)); } catch (e) { setErro(e); }
  };
  if (!d) return erro ? <ErroBox erro={erro} /> : <Carregando />;
  const av = d.avaliacao;
  return (
    <div>
      <Cartao titulo="Riscos especiais declarados">
        <p className="nota">Declare todos os riscos aplicáveis. Cada risco gera verificações obrigatórias que bloqueiam a aprovação até serem confirmadas pelo engenheiro responsável.</p>
        <div className="grade g2">
          {Object.entries(d.tipos).map(([k, v]) => (
            <label key={k}><input type="checkbox" disabled={!editavel} checked={!!d.riscos[k]} onChange={(e) => enviar({ riscos: { ...d.riscos, [k]: e.target.checked } })} /> {v as string}</label>
          ))}
        </div>
      </Cartao>
      <ErroBox erro={erro} />
      {av.bloqueios.map((b: string, i: number) => <Alerta key={i} tipo="erro">{b}</Alerta>)}
      {av.liberado && <Alerta tipo="ok">Nenhuma pendência de segurança para os riscos declarados.</Alerta>}
      {av.aplicaveis.map((a: any) => (
        <Cartao key={a.risco} titulo={a.titulo} acoes={<span className="nota">{a.referencias}</span>}>
          {!engenheiro && <p className="nota">Somente o engenheiro responsável marca os itens.</p>}
          <table>
            <tbody>{a.itens.map((it: any) => (
              <tr key={it.chave}>
                <td style={{ width: 30 }}><input type="checkbox" disabled={!engenheiro} checked={it.ok} onChange={(e) => enviar({ checklist: { [it.chave]: e.target.checked } })} /></td>
                <td>{it.texto}</td>
                <td>{it.ok ? <Selo tipo="ok">confirmado por {it.por} em {dataHora(it.em)}</Selo> : <Selo tipo="erro">pendente</Selo>}</td>
              </tr>
            ))}</tbody>
          </table>
        </Cartao>
      ))}
      <p className="nota">As referências normativas são indicativas; verifique as edições vigentes e as exigências locais. O software não substitui as análises de risco.</p>
    </div>
  );
}
