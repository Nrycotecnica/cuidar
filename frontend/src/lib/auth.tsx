import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, definirAoExpirar, gravarToken, lerToken } from "./api";

export interface Usuario {
  id: number;
  email: string;
  nome: string;
  perfil: string;
  perfil_nome: string;
  permissoes: string[];
  registro_profissional?: string | null;
}

interface Ctx {
  usuario: Usuario | null;
  carregando: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => void;
  pode: (perm: string) => boolean;
}

const AuthCtx = createContext<Ctx>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    definirAoExpirar(() => setUsuario(null));
    if (!lerToken()) {
      setCarregando(false);
      return;
    }
    api.get<Usuario>("/auth/eu").then(setUsuario).catch(() => setUsuario(null)).finally(() => setCarregando(false));
  }, []);

  const entrar = useCallback(async (email: string, senha: string) => {
    const r = await api.post<{ token: string; usuario: Usuario }>("/auth/login", { email, senha });
    gravarToken(r.token);
    setUsuario(r.usuario);
  }, []);

  const sair = useCallback(() => {
    gravarToken(null);
    setUsuario(null);
  }, []);

  const pode = useCallback((p: string) => !!usuario?.permissoes.includes(p), [usuario]);

  return <AuthCtx.Provider value={{ usuario, carregando, entrar, sair, pode }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
