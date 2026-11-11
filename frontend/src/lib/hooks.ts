import { useCallback, useEffect, useState } from "react";
import { ErroApi } from "./api";

/** Carrega dados de forma assíncrona com estado de erro/carregamento e recarga manual. */
export function useCarregar<T>(fn: () => Promise<T>, deps: any[] = []) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const recarregar = useCallback(async () => {
    setCarregando(true);
    try {
      setDados(await fn());
      setErro(null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setCarregando(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    recarregar();
  }, [recarregar]);
  return { dados, setDados, erro, carregando, recarregar };
}

export function textoErro(e: unknown): string {
  if (e instanceof ErroApi) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}
