import { useState, type ReactNode } from "react";
import { textoErro } from "../lib/hooks";
import { STATUS_PROJETO } from "../lib/format";
import { ErroApi } from "../lib/api";

export function SeloDemo({ ativo = true }: { ativo?: boolean }) {
  if (!ativo) return null;
  return <span className="selo selo-demo" title="Dados fictícios — não usar em projeto real">DEMONSTRATIVO — FICTÍCIO</span>;
}

export function SeloStatus({ status }: { status: string }) {
  return <span className={`selo st-${status}`}>{STATUS_PROJETO[status] || status}</span>;
}

export function Selo({ children, tipo = "neutro", title }: { children: ReactNode; tipo?: string; title?: string }) {
  return <span className={`selo selo-${tipo}`} title={title}>{children}</span>;
}

export function Alerta({ tipo = "info", children }: { tipo?: "info" | "erro" | "aviso" | "ok"; children: ReactNode }) {
  if (!children) return null;
  return <div className={`alerta alerta-${tipo}`}>{children}</div>;
}

export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return <div className="carregando">{texto}</div>;
}

export function Cartao({ titulo, acoes, children, className = "" }: { titulo?: ReactNode; acoes?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`cartao ${className}`}>
      {(titulo || acoes) && (
        <header className="cartao-cab">
          {titulo && <h3>{titulo}</h3>}
          {acoes && <div className="acoes">{acoes}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Campo({ rotulo, children, dica }: { rotulo: string; children: ReactNode; dica?: string }) {
  return (
    <label className="campo">
      <span className="rotulo">{rotulo}</span>
      {children}
      {dica && <span className="dica">{dica}</span>}
    </label>
  );
}

/** Botão que executa ação assíncrona mostrando estado e erro. */
export function BotaoAcao({
  onClick, children, className = "btn", disabled, title, confirmar,
}: { onClick: () => Promise<any> | void; children: ReactNode; className?: string; disabled?: boolean; title?: string; confirmar?: string }) {
  const [ocupado, setOcupado] = useState(false);
  return (
    <button
      className={className}
      disabled={disabled || ocupado}
      title={title}
      onClick={async () => {
        if (confirmar && !window.confirm(confirmar)) return;
        setOcupado(true);
        try {
          await onClick();
        } finally {
          setOcupado(false);
        }
      }}
    >
      {ocupado ? "Aguarde…" : children}
    </button>
  );
}

export function ErroBox({ erro }: { erro: unknown }) {
  if (!erro) return null;
  const pend = erro instanceof ErroApi ? erro.pendencias : undefined;
  return (
    <div className="alerta alerta-erro">
      {typeof erro === "string" ? erro : textoErro(erro)}
      {pend && pend.length > 0 && (
        <ul>
          {pend.map((p, i) => <li key={i}>{p}</li>)}
        </ul>
      )}
    </div>
  );
}

export function Abas({ abas, ativa, onChange }: { abas: { id: string; rotulo: string; oculto?: boolean }[]; ativa: string; onChange: (id: string) => void }) {
  return (
    <nav className="abas">
      {abas.filter((a) => !a.oculto).map((a) => (
        <button key={a.id} className={a.id === ativa ? "aba ativa" : "aba"} onClick={() => onChange(a.id)}>
          {a.rotulo}
        </button>
      ))}
    </nav>
  );
}

export function Vazio({ children }: { children: ReactNode }) {
  return <div className="vazio">{children}</div>;
}
