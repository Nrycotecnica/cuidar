import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { NOME_SOFTWARE, PROGRAMADOR, SUBTITULO } from "../lib/marca";

interface Versao { versao: string; ambiente: string; git_sha: string; versao_motor: string }

const NOME_AMB: Record<string, string> = {
  desenvolvimento: "DESENVOLVIMENTO",
  homologacao: "HOMOLOGAÇÃO — ambiente de testes",
  producao: "PRODUÇÃO",
};

export function Logo() {
  return (
    <svg className="logo" viewBox="0 0 32 32" width="34" height="34" aria-hidden>
      <circle cx="16" cy="16" r="14" fill="#2a5a87" />
      <path d="M16 2a14 14 0 0 1 0 28z" fill="#ff6b5e" />
      <circle cx="16" cy="16" r="4" fill="#fff" />
    </svg>
  );
}

export function FaixaAmbiente() {
  const [v, setV] = useState<Versao | null>(null);
  useEffect(() => {
    api.get<Versao>("/versao").then(setV).catch(() => {});
  }, []);
  if (!v) return <div className="faixa-amb amb-desconhecido">&nbsp;</div>;
  return (
    <div className={`faixa-amb amb-${v.ambiente}`} data-testid="faixa-ambiente">
      <strong>{NOME_AMB[v.ambiente] || v.ambiente.toUpperCase()}</strong>
      <span>versão {v.versao} · {v.git_sha} · motor de cálculo {v.versao_motor}</span>
    </div>
  );
}

export function Rodape() {
  return (
    <footer className="rodape" data-testid="rodape">
      <strong>{NOME_SOFTWARE}</strong> · Desenvolvido por {PROGRAMADOR}
    </footer>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { usuario, sair, pode } = useAuth();
  const [menu, setMenu] = useState(false);
  const itens = [
    { to: "/", rot: "Painel", ok: true },
    { to: "/projetos", rot: "Projetos", ok: true },
    { to: "/visitas", rot: "Visitas técnicas", ok: true },
    { to: "/clientes", rot: "Clientes", ok: true },
    { to: "/catalogo", rot: "Catálogo técnico", ok: true },
    { to: "/antigos", rot: "Projetos anteriores", ok: true },
    { to: "/admin", rot: "Administração", ok: pode("admin.ver") },
  ];
  return (
    <div className="app">
      <FaixaAmbiente />
      <div className="app-corpo">
        <aside className={menu ? "lateral aberta" : "lateral"}>
          <div className="marca">
            <Logo />
            <div>
              <div className="marca-nome">{NOME_SOFTWARE}</div>
              <div className="marca-sub">{SUBTITULO}</div>
            </div>
          </div>
          <nav onClick={() => setMenu(false)}>
            {itens.filter((i) => i.ok).map((i) => (
              <NavLink key={i.to} to={i.to} end={i.to === "/"} className={({ isActive }) => (isActive ? "nav ativo" : "nav")}>
                {i.rot}
              </NavLink>
            ))}
          </nav>
          <div className="usuario">
            <div className="usuario-nome">{usuario?.nome}</div>
            <div className="usuario-perfil">{usuario?.perfil_nome}</div>
            <button className="btn btn-mini" onClick={sair}>Sair</button>
          </div>
        </aside>
        <main className="conteudo">
          <button className="btn btn-mini menu-movel" onClick={() => setMenu(!menu)}>☰ Menu</button>
          {children}
        </main>
      </div>
      <Rodape />
    </div>
  );
}
