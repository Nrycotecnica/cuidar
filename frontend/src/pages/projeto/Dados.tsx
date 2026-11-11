import { useEffect, useState } from "react";
import { Alerta, BotaoAcao, Campo, Cartao, ErroBox } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { numero, STATUS_ENTRADA } from "../../lib/format";
import type { CtxProjeto } from "./Projeto";

const TEXTO = new Set(["contaminante", "material_dutos", "uso", "modo_pressao"]);
const OPCOES: Record<string, [string, string][]> = {
  contaminante: [["poeira_madeira", "Poeira de madeira"], ["poeira_metalica", "Poeira metálica"], ["poeira_leve", "Poeira leve"]],
  material_dutos: [["galvanizado", "Aço galvanizado"], ["aco_carbono", "Aço carbono"], ["inox", "Aço inox"], ["pvc", "PVC"]],
  uso: [["industrial_geral", "Industrial geral"], ["deposito", "Depósito"], ["fundicao", "Fundição"]],
  modo_pressao: [["negativa", "Negativa"], ["positiva", "Positiva"], ["neutra", "Neutra"]],
};

export default function Dados({ ctx }: { ctx: CtxProjeto }) {
  const { projeto: p, recarregar } = ctx;
  const { pode } = useAuth();
  const editavel = pode("projetos.editar") && !["aprovado", "liberado_fabricacao"].includes(p.status);
  const [cab, setCab] = useState({ nome: p.nome, cliente_id: p.cliente_id ?? "", descricao: p.descricao || "" });
  const [ent, setEnt] = useState<Record<string, any>>({});
  const [clientes, setClientes] = useState<any[]>([]);
  const [erro, setErro] = useState<unknown>(null);
  const [ok, setOk] = useState<string | null>(null);
  useEffect(() => {
    api.get<any[]>("/clientes").then(setClientes).catch(() => {});
    const e: Record<string, any> = {};
    for (const c of p.campos_entrada) {
      const v = p.entradas?.[c.chave] || {};
      e[c.chave] = { valor: v.valor ?? "", status: v.status || "nao_confirmado", fonte: v.fonte || "" };
    }
    setEnt(e);
  }, [p]);

  const salvar = async () => {
    setErro(null);
    setOk(null);
    try {
      await api.put(`/projetos/${p.id}`, { ...cab, cliente_id: cab.cliente_id ? Number(cab.cliente_id) : null });
      const corpo: Record<string, any> = {};
      for (const c of p.campos_entrada) {
        const v = ent[c.chave];
        if (!v) continue;
        const valor = TEXTO.has(c.chave) ? (v.valor || null) : numero(v.valor);
        const antes = p.entradas?.[c.chave];
        if (valor === null && !antes) continue;
        corpo[c.chave] = { valor, status: v.status, fonte: v.fonte || null };
      }
      await api.put(`/projetos/${p.id}/entradas`, corpo);
      await recarregar();
      setOk("Dados salvos.");
    } catch (e) {
      setErro(e);
    }
  };

  const nConf = p.campos_entrada.filter((c: any) => p.entradas?.[c.chave]?.status !== "confirmado").length;
  return (
    <div>
      <Cartao titulo="Identificação">
        <div className="grade g3">
          <Campo rotulo="Nome"><input value={cab.nome} disabled={!editavel} onChange={(e) => setCab({ ...cab, nome: e.target.value })} /></Campo>
          <Campo rotulo="Cliente">
            <select value={cab.cliente_id} disabled={!editavel} onChange={(e) => setCab({ ...cab, cliente_id: e.target.value })}>
              <option value="">— sem cliente —</option>
              {clientes.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Sistema"><input value={p.modulo_nome} disabled /></Campo>
        </div>
        <Campo rotulo="Descrição"><textarea value={cab.descricao} disabled={!editavel} onChange={(e) => setCab({ ...cab, descricao: e.target.value })} /></Campo>
      </Cartao>
      <Cartao titulo="Dados de entrada do cálculo">
        {nConf > 0 && <Alerta tipo="aviso">{nConf} dado(s) ainda não confirmado(s). Cálculos que dependem deles não podem ser aprovados.</Alerta>}
        {!pode("projetos.aprovar") && <p className="nota">Somente o engenheiro responsável pode marcar um dado como "confirmado"; alterações de valor por outros perfis voltam o status para "não confirmado".</p>}
        <table>
          <thead><tr><th>Dado</th><th style={{ width: 190 }}>Valor</th><th>Unid.</th><th style={{ width: 160 }}>Situação</th><th>Fonte / justificativa</th></tr></thead>
          <tbody>
            {p.campos_entrada.map((c: any) => {
              const v = ent[c.chave] || { valor: "", status: "nao_confirmado", fonte: "" };
              const st = p.entradas?.[c.chave] ? p.entradas[c.chave].status : "ausente";
              const upd = (k: string, val: string) => setEnt({ ...ent, [c.chave]: { ...v, [k]: val } });
              return (
                <tr key={c.chave} className={`ent-${st}`}>
                  <td>{c.rotulo}{c.obrigatorio && <strong title="obrigatório para o cálculo"> *</strong>}</td>
                  <td>
                    {OPCOES[c.chave] ? (
                      <select value={v.valor} disabled={!editavel} onChange={(e) => upd("valor", e.target.value)}>
                        <option value="">—</option>
                        {OPCOES[c.chave].map(([k, r]) => <option key={k} value={k}>{r}</option>)}
                        {v.valor && !OPCOES[c.chave].some(([k]) => k === v.valor) && <option value={v.valor}>{v.valor}</option>}
                      </select>
                    ) : (
                      <input inputMode="decimal" value={String(v.valor ?? "").replace(".", ",")} disabled={!editavel} onChange={(e) => upd("valor", e.target.value)} />
                    )}
                  </td>
                  <td>{c.unidade}</td>
                  <td>
                    <select value={v.status} disabled={!editavel} onChange={(e) => upd("status", e.target.value)}>
                      {Object.entries(STATUS_ENTRADA).map(([k, r]) => (
                        <option key={k} value={k} disabled={k === "confirmado" && !pode("projetos.aprovar") && p.entradas?.[c.chave]?.status !== "confirmado"}>{r}</option>
                      ))}
                    </select>
                  </td>
                  <td><input value={v.fonte} disabled={!editavel} onChange={(e) => upd("fonte", e.target.value)} placeholder="medição, planta, informação do cliente…" /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="nota">* obrigatório para o cálculo. Contaminantes e usos disponíveis correspondem aos parâmetros técnicos cadastrados.</p>
        <ErroBox erro={erro} />
        {ok && <Alerta tipo="ok">{ok}</Alerta>}
        {editavel && <div className="acoes"><BotaoAcao className="btn btn-primario" onClick={salvar}>Salvar dados</BotaoAcao></div>}
        {!editavel && ["aprovado", "liberado_fabricacao"].includes(p.status) && <Alerta tipo="info">Projeto aprovado: para editar, reabra-o na aba Aprovação (gera nova revisão).</Alerta>}
      </Cartao>
    </div>
  );
}
