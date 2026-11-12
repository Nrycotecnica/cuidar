// Cliente HTTP da API com token Bearer e mensagens de erro em português.

const CHAVE_TOKEN = "vent_token";

export function lerToken(): string | null {
  try {
    return localStorage.getItem(CHAVE_TOKEN);
  } catch {
    return null;
  }
}

export function gravarToken(t: string | null) {
  try {
    if (t) localStorage.setItem(CHAVE_TOKEN, t);
    else localStorage.removeItem(CHAVE_TOKEN);
  } catch {
    /* armazenamento indisponível: sessão só em memória */
  }
  tokenMemoria = t;
}

let tokenMemoria: string | null = lerToken();
let aoExpirar: (() => void) | null = null;
export function definirAoExpirar(f: () => void) {
  aoExpirar = f;
}

export class ErroApi extends Error {
  status: number;
  pendencias?: string[];
  constructor(status: number, mensagem: string, pendencias?: string[]) {
    super(mensagem);
    this.status = status;
    this.pendencias = pendencias;
  }
}

export function mensagemDeErro(status: number, corpo: any): { msg: string; pendencias?: string[] } {
  const d = corpo?.detail;
  if (typeof d === "string") return { msg: d };
  if (d && typeof d === "object" && !Array.isArray(d)) {
    return { msg: d.mensagem || "Erro", pendencias: Array.isArray(d.pendencias) ? d.pendencias : undefined };
  }
  if (Array.isArray(d)) {
    const itens = d.map((e: any) => {
      const campo = Array.isArray(e.loc) ? e.loc.filter((x: any) => x !== "body").join(".") : "";
      return `${campo ? campo + ": " : ""}${traduzirValidacao(e.msg || "")}`;
    });
    return { msg: "Dados inválidos — " + itens.join("; ") };
  }
  if (status === 401) return { msg: "Sessão expirada. Entre novamente." };
  if (status === 403) return { msg: "Seu perfil não tem permissão para esta ação." };
  if (status === 404) return { msg: "Registro não encontrado." };
  if (status === 413) return { msg: "Arquivo muito grande." };
  if (status >= 500) return { msg: "Erro interno do servidor. Tente novamente ou contate o administrador." };
  return { msg: `Erro ${status}` };
}

function traduzirValidacao(m: string): string {
  if (/field required/i.test(m)) return "campo obrigatório";
  if (/valid integer/i.test(m)) return "deve ser um número inteiro";
  if (/valid number/i.test(m)) return "deve ser um número";
  if (/valid string/i.test(m)) return "deve ser um texto";
  return m;
}

async function requisitar(metodo: string, url: string, corpo?: any, isForm = false): Promise<Response> {
  const headers: Record<string, string> = {};
  if (tokenMemoria) headers["Authorization"] = `Bearer ${tokenMemoria}`;
  let body: BodyInit | undefined;
  if (corpo !== undefined) {
    if (isForm) body = corpo as FormData;
    else {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(corpo);
    }
  }
  let r: Response;
  try {
    r = await fetch(url, { method: metodo, headers, body });
  } catch {
    throw new ErroApi(0, "Sem conexão com o servidor.");
  }
  if (!r.ok) {
    let j: any = null;
    try {
      j = await r.json();
    } catch {
      /* corpo não JSON */
    }
    if (r.status === 401 && !url.endsWith("/auth/login")) {
      gravarToken(null);
      aoExpirar?.();
    }
    const { msg, pendencias } = mensagemDeErro(r.status, j);
    throw new ErroApi(r.status, msg, pendencias);
  }
  return r;
}

export const api = {
  get: async <T = any>(url: string): Promise<T> => (await requisitar("GET", "/api" + url)).json(),
  post: async <T = any>(url: string, corpo: any = {}): Promise<T> => (await requisitar("POST", "/api" + url, corpo)).json(),
  put: async <T = any>(url: string, corpo: any): Promise<T> => (await requisitar("PUT", "/api" + url, corpo)).json(),
  del: async <T = any>(url: string): Promise<T> => (await requisitar("DELETE", "/api" + url)).json(),
  enviar: async <T = any>(url: string, form: FormData): Promise<T> => (await requisitar("POST", "/api" + url, form, true)).json(),
  blob: async (url: string): Promise<Blob> => (await requisitar("GET", "/api" + url)).blob(),
  baixar: async (url: string, nomePadrao: string, corpo?: any) => {
    // com corpo: POST (ex.: apresentação, que leva as imagens 3D do navegador)
    const r = await requisitar(corpo === undefined ? "GET" : "POST", "/api" + url, corpo);
    const cd = r.headers.get("Content-Disposition") || "";
    const m = /filename="?([^"]+)"?/.exec(cd);
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : nomePadrao;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  },
};
