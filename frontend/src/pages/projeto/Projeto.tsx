import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Abas, Alerta, Carregando, SeloDemo, SeloStatus } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import Dados from "./Dados";
import Plantas from "./Plantas";
import Rede from "./Rede";
import Calculo from "./Calculo";
import Documentos from "./Documentos";
import Seguranca from "./Seguranca";
import Aprovacao from "./Aprovacao";
import Assistente from "./Assistente";
import Historico from "./Historico";

// three.js pesa ~600 kB: só é baixado quando alguém abre a aba 3D
const Vista3D = lazy(() => import("./Vista3D"));

export interface CtxProjeto {
  projeto: any;
  recarregar: () => Promise<void>;
  calculos: any[];
  recarregarCalculos: () => Promise<void>;
  calcId: number | null;
  setCalcId: (id: number | null) => void;
  irPara: (aba: string) => void;
}

export default function Projeto() {
  const { id, aba = "dados" } = useParams();
  const nav = useNavigate();
  const { pode } = useAuth();
  const [projeto, setProjeto] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [calculos, setCalculos] = useState<any[]>([]);
  const [calcId, setCalcId] = useState<number | null>(null);

  const recarregar = useCallback(async () => {
    try {
      setProjeto(await api.get(`/projetos/${id}`));
    } catch (e: any) {
      setErro(e.message);
    }
  }, [id]);
  const recarregarCalculos = useCallback(async () => {
    const l = await api.get<any[]>(`/projetos/${id}/calculos`).catch(() => []);
    setCalculos(l);
    setCalcId((atual) => (atual && l.some((c) => c.id === atual) ? atual : l[0]?.id ?? null));
  }, [id]);
  useEffect(() => {
    setProjeto(null);
    setCalcId(null);
    recarregar();
    recarregarCalculos();
  }, [recarregar, recarregarCalculos]);

  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!projeto) return <Carregando />;
  const irPara = (a: string) => nav(`/projetos/${id}/${a}`);
  const ctx: CtxProjeto = { projeto, recarregar, calculos, recarregarCalculos, calcId, setCalcId, irPara };
  const abas = [
    { id: "dados", rotulo: "Dados" },
    { id: "plantas", rotulo: "Plantas" },
    { id: "rede", rotulo: projeto.modulo === "renovacao" ? "Rede / layout" : "Rede de dutos" },
    { id: "3d", rotulo: "3D" },
    { id: "calculo", rotulo: "Cálculo" },
    { id: "documentos", rotulo: "Documentos" },
    { id: "seguranca", rotulo: "Segurança" },
    { id: "aprovacao", rotulo: "Aprovação" },
    { id: "assistente", rotulo: "Assistente", oculto: !pode("assistente.usar") },
    { id: "historico", rotulo: "Histórico" },
  ];
  return (
    <div>
      <div className="cabecalho">
        <div>
          <h1>{projeto.codigo} — {projeto.nome}</h1>
          <div className="sub">
            {projeto.modulo_nome} · {projeto.cliente_nome || "sem cliente"} · revisão {projeto.versao} · <SeloStatus status={projeto.status} /> <SeloDemo ativo={projeto.demonstrativo} />
          </div>
        </div>
      </div>
      {projeto.demonstrativo && (
        <Alerta tipo="aviso">Projeto DEMONSTRATIVO com dados fictícios: os resultados não podem ser usados em instalação e o projeto não pode ser aprovado.</Alerta>
      )}
      <Abas abas={abas} ativa={aba} onChange={irPara} />
      {aba === "dados" && <Dados ctx={ctx} />}
      {aba === "plantas" && <Plantas ctx={ctx} />}
      {aba === "rede" && <Rede ctx={ctx} />}
      {aba === "3d" && <Suspense fallback={<Carregando texto="Abrindo a vista 3D…" />}><Vista3D ctx={ctx} /></Suspense>}
      {aba === "calculo" && <Calculo ctx={ctx} />}
      {aba === "documentos" && <Documentos ctx={ctx} />}
      {aba === "seguranca" && <Seguranca ctx={ctx} />}
      {aba === "aprovacao" && <Aprovacao ctx={ctx} />}
      {aba === "assistente" && <Assistente ctx={ctx} />}
      {aba === "historico" && <Historico ctx={ctx} />}
    </div>
  );
}
