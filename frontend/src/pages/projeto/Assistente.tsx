import { useEffect, useRef, useState } from "react";
import { Alerta, Cartao, ErroBox, Selo } from "../../components/ui";
import { api } from "../../lib/api";
import type { CtxProjeto } from "./Projeto";

const SUGESTOES = [
  "Preciso projetar uma exaustão de poeira para este galpão.",
  "Analise a planta e sugira o posicionamento dos dutos.",
  "Compare dois exaustores que a empresa fabrica.",
  "Reduza o comprimento da tubulação sem comprometer o dimensionamento.",
  "Gere outra alternativa com menor custo.",
  "Explique por que este exaustor foi selecionado.",
  "O que falta para aprovar este projeto?",
];

interface Msg { role: "user" | "assistant"; content: string; ferramentas?: string[] }

export default function Assistente({ ctx }: { ctx: CtxProjeto }) {
  const [status, setStatus] = useState<any>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [texto, setTexto] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<unknown>(null);
  const fim = useRef<HTMLDivElement>(null);
  useEffect(() => { api.get("/assistente/status").then(setStatus).catch(() => {}); }, []);
  useEffect(() => { fim.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [msgs]);
  const enviar = async (t: string) => {
    if (!t.trim() || ocupado) return;
    const hist: Msg[] = [...msgs, { role: "user", content: t.trim() }];
    setMsgs(hist);
    setTexto("");
    setOcupado(true);
    setErro(null);
    try {
      const r = await api.post(`/projetos/${ctx.projeto.id}/assistente`, { mensagens: hist.map(({ role, content }) => ({ role, content })) });
      setMsgs([...hist, { role: "assistant", content: r.resposta, ferramentas: r.ferramentas }]);
    } catch (e) { setErro(e); } finally { setOcupado(false); }
  };
  return (
    <Cartao titulo="Assistente técnico" acoes={status && (status.modo === "ia" ? <Selo tipo="ok">IA ativa · {status.modelo}</Selo> : <Selo tipo="aviso">Modo de regras (sem IA)</Selo>)}>
      <Alerta tipo="info">
        O assistente consulta somente dados do projeto, resultados do motor de cálculo e o catálogo. Ele <strong>não calcula valores por conta própria,
        não inventa parâmetros e não aprova nem libera projetos</strong>. {status?.mensagem}
      </Alerta>
      <div className="sugestoes">
        {SUGESTOES.map((s) => <button key={s} className="btn btn-mini" onClick={() => enviar(s)} disabled={ocupado}>{s}</button>)}
      </div>
      <div className="chat" data-testid="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.content}
            {m.ferramentas && m.ferramentas.length > 0 && <div className="nota" style={{ marginTop: 6 }}>Consultas: {Array.from(new Set(m.ferramentas)).join(", ")}</div>}
          </div>
        ))}
        {ocupado && <div className="msg assistant nota">Analisando…</div>}
        <div ref={fim} />
      </div>
      <ErroBox erro={erro} />
      <form className="form-linha" style={{ marginTop: 8 }} onSubmit={(e) => { e.preventDefault(); enviar(texto); }}>
        <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Pergunte sobre este projeto…" style={{ flex: 1 }} />
        <button className="btn btn-primario" disabled={ocupado || !texto.trim()}>Enviar</button>
      </form>
    </Cartao>
  );
}
