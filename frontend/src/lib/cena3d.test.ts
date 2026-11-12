import { describe, expect, it } from "vitest";
import { montarCena } from "./cena3d";

// Mesmo caso de backend/tests/test_engine.py (test_rede_com_cotas_conta_descidas_e_curvas):
// se a vista 3D e o cálculo divergirem nas descidas, um dos dois testes quebra.
function referencia() {
  return {
    nodes: [
      { id: "c1", type: "captor", x: 0, y: 0, label: "C1" },
      { id: "f", type: "exaustor", x: 10, y: 0 },
      { id: "d", type: "descarga", x: 15, y: 0 },
    ],
    segments: [
      { id: "s1", from: "c1", to: "f", diametro_mm: 300 },
      { id: "s2", from: "f", to: "d", diametro_mm: 300 },
    ],
  } as any;
}

describe("cena 3D a partir das cotas", () => {
  it("descidas e subidas iguais às do cálculo", () => {
    const r = referencia();
    r.cotas = { rede_m: 4 };
    r.nodes[0].z_m = 1; r.nodes[1].z_m = 4; r.nodes[2].z_m = 9;
    const c = montarCena(r, null, 7);
    expect(c.ilustrativa).toBe(false);
    const [s1, s2] = c.tubos;
    expect(s1.verticalM).toBeCloseTo(3);
    expect(s2.verticalM).toBeCloseTo(5);
    expect(s1.pontos).toEqual([[0, 0, 1], [0, 0, 4], [10, 0, 4]]);
    expect(s2.pontos).toEqual([[10, 0, 4], [15, 0, 4], [15, 0, 9]]);
    expect(s1.lado).toBe("succao");
    expect(s2.lado).toBe("descarga");
    expect(s1.diametroM).toBeCloseTo(0.3);
  });

  it("nó sem cota: sem descida e listado, como no cálculo", () => {
    const r = referencia();
    r.cotas = { rede_m: 4 };
    r.nodes[0].z_m = 1;
    const c = montarCena(r, null, null);
    expect(c.semCota).toEqual(["d", "f"]);
    expect(c.tubos[1].verticalM).toBe(0);
    expect(c.pecas.find((p) => p.id === "f")?.semCota).toBe(true);
  });

  it("sem cota da rede: alturas só ilustrativas, a partir do pé-direito", () => {
    const c = montarCena(referencia(), null, 8);
    expect(c.ilustrativa).toBe(true);
    expect(c.cotaRede).toBeCloseTo(4.8);
    expect(c.semCota).toEqual([]);
  });

  it("diâmetro do cálculo prevalece; sem diâmetro, marca como não definido", () => {
    const r = referencia();
    delete r.segments[0].diametro_mm;
    const c = montarCena(r, { trechos: [{ id: "s2", diametro_mm: 450 }] }, null);
    expect(c.tubos[0].diametroInformado).toBe(false);
    expect(c.tubos[1].diametroM).toBeCloseTo(0.45);
  });

  it("trecho com cota própria desce até a junção", () => {
    const r = {
      cotas: { rede_m: 5 },
      nodes: [
        { id: "c1", type: "captor", x: 0, y: 0, z_m: 1 },
        { id: "j", type: "juncao", x: 4, y: 0 },
        { id: "e", type: "exaustor", x: 8, y: 0, z_m: 5 },
      ],
      segments: [
        { id: "a", from: "c1", to: "j", cota_m: 3 },
        { id: "b", from: "j", to: "e" },
      ],
    };
    const c = montarCena(r, null, null);
    // a junção fica na cota do trecho que sai dela (5 m): o ramal a 3 m sobe 2 m nela
    expect(c.tubos[0].verticalM).toBeCloseTo(2 + 2);
    expect(c.tubos[1].verticalM).toBe(0);
  });
});
