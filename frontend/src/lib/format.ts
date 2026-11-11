// Formatação numérica pt-BR
export function fmt(v: number | null | undefined, casas = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

export function numero(s: string | number | null | undefined): number | null {
  if (s === null || s === undefined) return null;
  if (typeof s === "number") return Number.isFinite(s) ? s : null;
  const t = s.trim().replace(/\s/g, "");
  if (!t) return null;
  const norm = t.includes(",") && t.includes(".") ? t.replace(/\./g, "").replace(",", ".") : t.replace(",", ".");
  const n = Number(norm);
  return Number.isFinite(n) ? n : null;
}

export function dataHora(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export const STATUS_PROJETO: Record<string, string> = {
  rascunho: "Rascunho",
  em_revisao: "Em revisão técnica",
  aprovado: "Aprovado tecnicamente",
  liberado_fabricacao: "Liberado para fabricação",
};

export const MODULOS: Record<string, string> = {
  poeira: "Exaustão de poeiras",
  fumos: "Fumaças, gases e vapores",
  renovacao: "Renovação de ar",
};

export const STATUS_ENTRADA: Record<string, string> = {
  confirmado: "Confirmado",
  estimado: "Estimado",
  nao_confirmado: "Não confirmado",
};

export const RISCOS: Record<string, string> = {
  poeira_combustivel: "Poeira combustível",
  atmosfera_explosiva: "Atmosfera explosiva (gases/vapores inflamáveis)",
  contaminante_perigoso: "Contaminante perigoso (tóxico/corrosivo/cancerígeno)",
  temperatura_elevada: "Temperatura elevada",
  controle_fumaca_incendio: "Controle de fumaça de incêndio",
};

export const TIPOS_CAPTOR: Record<string, string> = {
  abertura_livre: "Abertura simples (sem flange)",
  abertura_flangeada: "Abertura com flange",
  enclausuramento: "Enclausuramento / cabine",
  coifa_baixa: "Coifa sobre fonte (fria)",
  vazao_informada: "Vazão informada manualmente",
};

export const ENTRADAS_CAPTOR: Record<string, string> = {
  flangeada: "Flangeada",
  livre: "Livre (duto simples)",
  boca_sino: "Boca de sino",
  coifa: "Coifa",
};
