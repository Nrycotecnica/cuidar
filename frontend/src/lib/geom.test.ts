import { describe, expect, it } from "vitest";
import { ajustar, distPontoSegmento, paraMundo, paraTela, pontoEmPoligono, zoomEm, retangulo } from "./geom";
import { fmt, numero, mensagemDeErroTeste } from "./testutil";

describe("geometria de visualização", () => {
  const v = { cx: 10, cy: 5, escala: 20, w: 800, h: 600 };
  it("ida e volta mundo↔tela", () => {
    const [sx, sy] = paraTela(v, 12, 7);
    const [x, y] = paraMundo(v, sx, sy);
    expect(x).toBeCloseTo(12);
    expect(y).toBeCloseTo(7);
  });
  it("y do mundo cresce para cima na tela", () => {
    expect(paraTela(v, 10, 6)[1]).toBeLessThan(paraTela(v, 10, 5)[1]);
  });
  it("zoom mantém o ponto sob o cursor", () => {
    const antes = paraMundo(v, 123, 456);
    const z = zoomEm(v, 123, 456, 1.7);
    const depois = paraMundo(z, 123, 456);
    expect(depois[0]).toBeCloseTo(antes[0]);
    expect(depois[1]).toBeCloseTo(antes[1]);
    expect(z.escala).toBeCloseTo(34);
  });
  it("ajustar enquadra a extensão", () => {
    const a = ajustar([0, 0, 100, 50], 1000, 500, 0);
    expect(a.escala).toBeCloseTo(10);
    expect(a.cx).toBe(50);
  });
  it("distância ponto-segmento e ponto em polígono", () => {
    expect(distPontoSegmento([5, 3], [0, 0], [10, 0])).toBeCloseTo(3);
    expect(pontoEmPoligono([1, 1], retangulo([0, 0], [2, 2]))).toBe(true);
    expect(pontoEmPoligono([3, 1], retangulo([0, 0], [2, 2]))).toBe(false);
  });
});

describe("formatação pt-BR", () => {
  it("formata e interpreta números", () => {
    expect(fmt(1234.5, 1)).toBe("1.234,5");
    expect(numero("1.234,5")).toBe(1234.5);
    expect(numero("2,5")).toBe(2.5);
    expect(numero("")).toBeNull();
    expect(numero("abc")).toBeNull();
  });
  it("traduz erros do backend", () => {
    expect(mensagemDeErroTeste(422, { detail: "Rede inválida" }).msg).toBe("Rede inválida");
    expect(mensagemDeErroTeste(409, { detail: { mensagem: "Aprovação bloqueada", pendencias: ["a"] } }).pendencias).toEqual(["a"]);
    expect(mensagemDeErroTeste(422, { detail: [{ loc: ["body", "nome"], msg: "Field required" }] }).msg).toContain("nome: campo obrigatório");
    expect(mensagemDeErroTeste(403, null).msg).toContain("permissão");
  });
});
