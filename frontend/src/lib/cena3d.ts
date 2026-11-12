// Geometria 3D da rede de dutos, a partir da planta (x, y) e das cotas.
//
// As regras de cota são as MESMAS de backend/app/engine/cotas.py — o cálculo
// soma as descidas que este arquivo desenha. Se uma mudar sem a outra, a vista
// 3D mostra um duto que o cálculo não considerou (ou o contrário), e o
// engenheiro aprova uma perda de carga que não corresponde ao desenho.
//
// Sem a cota da rede, o projeto ainda não tem alturas: a cena é montada com
// alturas ILUSTRATIVAS (só para enxergar o traçado) e marcada como tal.

export type P3 = [number, number, number]; // x, y (planta), z (altura) — metros

export const TIPOS_COM_COTA_PROPRIA = new Set(["captor", "filtro", "exaustor", "descarga", "equipamento"]);
const TOLERANCIA_M = 0.005;

// Alturas usadas só quando o projeto não tem cotas. Não entram em cálculo.
export const ILUSTRATIVO = { captor: 1.0, equipamento: 1.5, acimaDaRede: 3.0, redePadrao: 4.0, obstaculo: 1.5 };

export interface Tubo {
  id: string;
  rotulo: string;
  pontos: P3[];
  diametroM: number;
  diametroInformado: boolean; // false = diâmetro ainda não definido (desenhado com valor ilustrativo)
  lado: "succao" | "descarga";
  verticalM: number;
}

export interface Peca {
  id: string;
  tipo: string;
  rotulo: string;
  pos: P3;
  semCota: boolean;
}

export interface Cena {
  ilustrativa: boolean; // true = sem cota da rede: alturas inventadas só para visualizar
  cotaRede: number;
  peDireito: number | null;
  tubos: Tubo[];
  pecas: Peca[];
  semCota: string[];
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

export function montarCena(dados: any, resultados: any | null, peDireito: number | null): Cena {
  const nodes: any[] = dados?.nodes || [];
  const segs: any[] = dados?.segments || [];
  const nos: Record<string, any> = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const informada = num(dados?.cotas?.rede_m);
  const ilustrativa = informada === null;
  const cotaRede = informada ?? (peDireito ? Math.round(peDireito * 0.6 * 10) / 10 : ILUSTRATIVO.redePadrao);

  const corrida = (s: any) => (ilustrativa ? cotaRede : num(s.cota_m) ?? cotaRede);
  const saida: Record<string, any> = {};
  const chegada: Record<string, any> = {};
  for (const s of segs) {
    saida[s.from] ??= s;
    chegada[s.to] ??= s;
  }
  // descarga: lado do exaustor em diante
  const lado: Record<string, "succao" | "descarga"> = {};
  const exaustor = nodes.find((n) => n.type === "exaustor");
  for (let cur = exaustor?.id, guarda = 0; cur && saida[cur] && guarda < 10000; guarda++) {
    lado[saida[cur].id] = "descarga";
    cur = saida[cur].to;
  }

  const cotaNo = (id: string): number | null => {
    const n = nos[id];
    if (!n) return null;
    if (TIPOS_COM_COTA_PROPRIA.has(n.type)) {
      if (!ilustrativa) return num(n.z_m);
      if (n.type === "captor") return ILUSTRATIVO.captor;
      if (n.type === "descarga") return cotaRede + ILUSTRATIVO.acimaDaRede;
      return ILUSTRATIVO.equipamento;
    }
    const s = saida[id] || chegada[id];
    return s ? corrida(s) : cotaRede;
  };

  const semCota = ilustrativa ? [] : nodes.filter((n) => TIPOS_COM_COTA_PROPRIA.has(n.type) && num(n.z_m) === null && (saida[n.id] || chegada[n.id])).map((n) => n.id).sort();

  const trechosRes: Record<string, any> = Object.fromEntries(((resultados?.trechos as any[]) || []).map((t) => [t.id, t]));
  const tubos: Tubo[] = [];
  for (const s of segs) {
    const a = nos[s.from], b = nos[s.to];
    if (!a || !b) continue;
    const z = corrida(s);
    const planta: [number, number][] = [[a.x, a.y], ...((s.path || []) as [number, number][]), [b.x, b.y]];
    const pts: P3[] = planta.map(([x, y]) => [x, y, z]);
    let vertical = 0;
    const za = cotaNo(s.from), zb = cotaNo(s.to);
    if (za !== null && Math.abs(za - z) > TOLERANCIA_M) { pts.unshift([a.x, a.y, za]); vertical += Math.abs(za - z); }
    if (zb !== null && Math.abs(zb - z) > TOLERANCIA_M) { pts.push([b.x, b.y, zb]); vertical += Math.abs(zb - z); }
    const t = trechosRes[s.id];
    const dmm = num(t?.diametro_mm) ?? num(s.diametro_mm);
    const w = num(t?.largura_mm) ?? num(s.largura_mm), h = num(t?.altura_mm) ?? num(s.altura_mm);
    // retangular: desenhado como tubo de mesma área (a vista é para ler o traçado, não a seção)
    const deq = dmm ?? (w && h ? Math.sqrt((4 * w * h) / Math.PI) : null);
    tubos.push({
      id: s.id, rotulo: s.label || s.id, pontos: pts,
      diametroM: (deq ?? 200) / 1000, diametroInformado: deq !== null,
      lado: lado[s.id] || "succao", verticalM: Math.round(vertical * 10000) / 10000,
    });
  }

  const pecas: Peca[] = nodes
    .filter((n) => n.type !== "ponto" && n.type !== "juncao")
    .map((n) => {
      const z = cotaNo(n.id);
      return { id: n.id, tipo: n.type, rotulo: n.label || n.id, pos: [n.x, n.y, z ?? cotaRede] as P3, semCota: z === null };
    });

  return { ilustrativa, cotaRede, peDireito, tubos, pecas, semCota };
}
