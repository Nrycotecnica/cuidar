import { useEffect, useState } from "react";
import Grafico from "../../components/Grafico";
import { Alerta, BotaoAcao, Carregando, Cartao, ErroBox, Selo, Vazio } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dataHora, fmt } from "../../lib/format";
import type { CtxProjeto } from "./Projeto";

export function SeletorCalculo({ ctx }: { ctx: CtxProjeto }) {
  if (!ctx.calculos.length) return null;
  return (
    <select value={ctx.calcId ?? ""} onChange={(e) => ctx.setCalcId(Number(e.target.value))} style={{ maxWidth: 520 }}>
      {ctx.calculos.map((c) => (
        <option key={c.id} value={c.id}>
          Nº {c.id} — {dataHora(c.criado_em)} — {c.tipo === "rede" ? "rede" : "renovação"} — {fmt(c.vazao_total_m3h)} m³/h{c.pressao_total_pa ? ` / ${fmt(c.pressao_total_pa)} Pa` : ""} — {c.situacao === "ok" ? "sem bloqueios" : `${c.bloqueios} bloqueio(s)`}
        </option>
      ))}
    </select>
  );
}

function Lista({ titulo, itens, tipo }: { titulo: string; itens?: string[]; tipo: "erro" | "aviso" | "info" }) {
  if (!itens?.length) return null;
  return <Alerta tipo={tipo}><strong>{titulo}</strong><ul>{itens.map((x, i) => <li key={i}>{x}</li>)}</ul></Alerta>;
}

export default function Calculo({ ctx }: { ctx: CtxProjeto }) {
  const { pode } = useAuth();
  const [calc, setCalc] = useState<any>(null);
  const [erro, setErro] = useState<unknown>(null);
  useEffect(() => {
    setCalc(null);
    if (ctx.calcId) api.get(`/calculos/${ctx.calcId}`).then(setCalc).catch(setErro);
  }, [ctx.calcId]);
  if (!ctx.calculos.length) return <Vazio>Nenhum cálculo executado. Monte a rede e clique em “Calcular” na aba Rede.</Vazio>;
  if (!calc) return <Carregando />;
  const r = calc.resultados;
  const usarExaustor = async (id: number) => {
    try {
      const c = await api.post(`/projetos/${ctx.projeto.id}/calcular`, { estrategia: r.estrategia, exaustor_id: id });
      await ctx.recarregarCalculos();
      ctx.setCalcId(c.id);
    } catch (e) { setErro(e); }
  };
  return (
    <div>
      <div className="form-linha" style={{ marginBottom: 10 }}>
        <SeletorCalculo ctx={ctx} />
        <span className="nota">motor v{calc.versao_motor} · software v{calc.versao_app} · hash <code>{calc.hash_entradas.slice(0, 16)}</code></span>
      </div>
      <ErroBox erro={erro} />
      <Lista titulo="Bloqueios (impedem aprovação)" itens={r.bloqueios} tipo="erro" />
      <Lista titulo="Avisos" itens={r.avisos} tipo="aviso" />
      {calc.tipo === "rede" ? <ResultadoRede r={r} podeCalcular={pode("calculos.executar")} usarExaustor={usarExaustor} /> : <ResultadoRenovacao r={r} />}
      <Cartao titulo="Hipóteses de cálculo"><ul>{(r.hipoteses || []).map((h: string, i: number) => <li key={i}>{h}</li>)}</ul></Cartao>
      <Cartao titulo="Dados de entrada utilizados">
        <table>
          <thead><tr><th>Dado</th><th>Valor</th><th>Situação</th></tr></thead>
          <tbody>{(r.entradas_usadas || []).map((e: any) => (
            <tr key={e.chave} className={`ent-${e.status}`}><td>{e.rotulo}</td><td>{e.valor ?? "—"}</td>
              <td>{e.status === "confirmado" ? <Selo tipo="ok">confirmado</Selo> : <Selo tipo="erro">{e.status.replace("_", " ")}</Selo>}</td></tr>
          ))}</tbody>
        </table>
      </Cartao>
      <Cartao titulo="Parâmetros técnicos utilizados">
        <table>
          <thead><tr><th>Chave</th><th className="num">Valor</th><th>Unid.</th><th>Status</th><th>Referência</th></tr></thead>
          <tbody>{(r.parametros_usados || []).map((p: any) => (
            <tr key={p.chave}><td><code>{p.chave}</code></td><td className="num">{String(p.valor)}</td><td>{p.unidade}</td>
              <td>{p.status === "aprovado" ? <Selo tipo="ok">aprovado</Selo> : <Selo tipo="aviso">proposto</Selo>} {p.demonstrativo && <Selo tipo="demo">demonstrativo</Selo>}</td>
              <td className="nota">{p.referencia}</td></tr>
          ))}</tbody>
        </table>
      </Cartao>
      <Cartao titulo="Memória de cálculo">
        <div className="tabela-rolagem">
          <table>
            <thead><tr><th>Descrição</th><th>Fórmula</th><th>Substituição</th><th className="num">Resultado</th></tr></thead>
            <tbody>{(r.passos || []).map((p: any, i: number) => (
              <tr key={i}><td>{p.descricao}</td><td><code>{p.formula}</code></td><td className="nota">{p.substituicao}</td>
                <td className="num">{typeof p.resultado === "number" ? fmt(p.resultado, 4) : p.resultado} {p.unidade}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </Cartao>
    </div>
  );
}

function ResultadoRede({ r, podeCalcular, usarExaustor }: { r: any; podeCalcular: boolean; usarExaustor: (id: number) => Promise<void> }) {
  const sel = r.selecao_exaustor || {};
  const s = sel.selecionado;
  const k = s ? (s.tipo_pressao_curva === "estatica" ? r.k_sistema_estatica : r.k_sistema_total) : r.k_sistema_estatica;
  const qmax = s ? Math.max(...s.curva_m3h_pa.map((p: number[]) => p[0])) : r.vazao_total_m3h * 1.5;
  const sistema: [number, number][] = Array.from({ length: 41 }, (_, i) => { const q = (qmax * i) / 40; return [q, k * (q / 3600) ** 2]; });
  return (
    <>
      <div className="indicadores">
        <div className="indicador"><div className="v">{fmt(r.vazao_total_m3h)}</div><div className="r">Vazão total (m³/h)</div></div>
        <div className="indicador"><div className="v">{fmt(r.pressao_total_ventilador_pa)}</div><div className="r">Pressão total do ventilador (Pa)</div></div>
        <div className="indicador"><div className="v">{fmt(r.pressao_estatica_ventilador_pa)}</div><div className="r">Pressão estática do ventilador (Pa)</div></div>
        <div className="indicador"><div className="v">{fmt(r.ar?.densidade, 3)}</div><div className="r">Densidade do ar (kg/m³)</div></div>
        <div className="indicador"><div className="v">{fmt(r.potencia_ar_kw, 2)}</div><div className="r">Potência transmitida ao ar (kW)</div></div>
      </div>
      <Cartao titulo="Seleção do exaustor (catálogo próprio)">
        {s ? (
          <Alerta tipo="ok">
            <strong>{s.nome}</strong> — ponto de operação {fmt(s.ponto_operacao.vazao_m3h)} m³/h a {fmt(s.ponto_operacao.pressao_pa)} Pa ({s.tipo_pressao_curva === "estatica" ? "estática" : "total"}),
            folga de vazão {fmt(s.folga_vazao_pct, 1)}%, potência absorvida {s.potencia_absorvida_kw != null ? fmt(s.potencia_absorvida_kw, 2) + " kW" : "sem dados"}.
            {sel.escolha_manual && " (escolhido manualmente)"}
            {s.ponto_operacao.multiplas_intersecoes && " Atenção: curva com mais de uma interseção — verificar estabilidade."}
          </Alerta>
        ) : <Alerta tipo="erro">{sel.mensagem || "Nenhum exaustor selecionado."}</Alerta>}
        <div className="grade g2">
          <div>
            {s ? (
              <Grafico series={[{ nome: "Exaustor (corrigido p/ densidade)", pontos: s.curva_m3h_pa, cor: "#1f4e79" }, { nome: "Curva do sistema", pontos: sistema, cor: "#c00000", tracejado: true }]}
                marcador={{ x: s.ponto_operacao.vazao_m3h, y: s.ponto_operacao.pressao_pa, rotulo: "ponto de operação" }}
                rotuloY={`Pressão ${s.tipo_pressao_curva === "estatica" ? "estática" : "total"} (Pa)`} />
            ) : (
              <Grafico series={[{ nome: "Curva do sistema (estática)", pontos: sistema, cor: "#c00000", tracejado: true }]}
                marcador={{ x: r.vazao_total_m3h, y: r.pressao_estatica_ventilador_pa, rotulo: "ponto de projeto" }} />
            )}
          </div>
          <div>
            <h3>Compatíveis</h3>
            <table>
              <thead><tr><th>Exaustor</th><th className="num">Q op.</th><th className="num">P op.</th><th className="num">kW</th><th></th></tr></thead>
              <tbody>{(sel.compativeis || []).map((c: any) => (
                <tr key={c.id}><td>{c.nome}</td><td className="num">{fmt(c.ponto_operacao.vazao_m3h)}</td><td className="num">{fmt(c.ponto_operacao.pressao_pa)}</td>
                  <td className="num">{fmt(c.potencia_absorvida_kw, 2)}</td>
                  <td>{s && c.id !== s.id && podeCalcular && <BotaoAcao className="btn btn-mini" onClick={() => usarExaustor(c.id)}>Usar este</BotaoAcao>}</td></tr>
              ))}</tbody>
            </table>
            {!(sel.compativeis || []).length && <p className="nota">Nenhum compatível.</p>}
            <h3 style={{ marginTop: 10 }}>Rejeitados</h3>
            <table>
              <tbody>{(sel.rejeitados || []).map((c: any, i: number) => <tr key={i}><td>{c.nome}</td><td className="nota">{c.motivo}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      </Cartao>
      <Cartao titulo="Captores">
        <table>
          <thead><tr><th>Captor</th><th className="num">Vazão (m³/h)</th><th className="num">Perda até o exaustor (Pa)</th><th></th></tr></thead>
          <tbody>{r.captores.map((c: any) => (
            <tr key={c.id}><td>{c.label}</td><td className="num">{fmt(c.vazao_m3h)}</td><td className="num">{fmt(c.perda_ate_exaustor_pa, 1)}</td><td>{c.governante && <Selo tipo="aviso">ramo governante</Selo>}</td></tr>
          ))}</tbody>
        </table>
      </Cartao>
      <Cartao titulo="Trechos">
        <div className="tabela-rolagem">
          <table>
            <thead><tr><th>Trecho</th><th>Lado</th><th>Seção</th><th className="num">Vazão m³/h</th><th className="num">v m/s</th><th className="num">VP Pa</th><th className="num">L m</th><th className="num">f</th><th className="num">ΣK</th><th className="num">Perda Pa</th><th>Singularidades</th></tr></thead>
            <tbody>{r.trechos.map((t: any) => (
              <tr key={t.id}><td>{t.label}</td><td>{t.lado === "succao" ? "sucção" : "descarga"}</td>
                <td>{t.diametro_mm ? `Ø${fmt(t.diametro_mm)}` : `${t.largura_mm}×${t.altura_mm}`}{t.dimensionado_auto && <span className="nota"> (auto)</span>}</td>
                <td className="num">{fmt(t.vazao_m3h)}</td><td className="num">{fmt(t.velocidade_ms, 2)}</td><td className="num">{fmt(t.vp_pa, 1)}</td>
                <td className="num">{fmt(t.comprimento_m, 2)}</td><td className="num">{fmt(t.fator_atrito, 4)}</td><td className="num">{fmt(t.k_total, 2)}</td>
                <td className="num">{fmt(t.perda_total_pa, 1)}</td><td className="nota">{t.singulares.map((x: any) => x.descricao).join("; ")}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </Cartao>
      {r.equilibrio?.length > 0 && (
        <Cartao titulo="Equilíbrio de pressões nas junções">
          <table>
            <thead><tr><th>Junção</th><th>Ramal</th><th className="num">Perda ramal</th><th className="num">Perda governante</th><th className="num">Razão</th><th>Situação</th></tr></thead>
            <tbody>{r.equilibrio.map((e: any, i: number) => (
              <tr key={i}><td>{e.juncao}</td><td>{e.trecho}</td><td className="num">{fmt(e.perda_ramal_pa, 1)}</td><td className="num">{fmt(e.perda_governante_pa, 1)}</td><td className="num">{fmt(e.razao, 2)}</td>
                <td className={e.situacao === "aceitavel" ? "" : "div-erro"}>{e.mensagem}</td></tr>
            ))}</tbody>
          </table>
        </Cartao>
      )}
    </>
  );
}

function ResultadoRenovacao({ r }: { r: any }) {
  if (r.volume_m3 === undefined) return null;
  return (
    <>
      <div className="indicadores">
        <div className="indicador"><div className="v">{fmt(r.volume_m3)}</div><div className="r">Volume (m³)</div></div>
        <div className="indicador"><div className="v">{fmt(r.vazao_requerida_m3h)}</div><div className="r">Vazão requerida (m³/h)</div></div>
        <div className="indicador"><div className="v">{fmt(r.vazao_exaustao_m3h)}</div><div className="r">Exaustão (m³/h)</div></div>
        <div className="indicador"><div className="v">{fmt(r.vazao_insuflamento_m3h)}</div><div className="r">Insuflamento (m³/h)</div></div>
        <div className="indicador"><div className="v">{fmt(r.trocas_hora_resultantes, 1)}</div><div className="r">Trocas por hora</div></div>
        <div className="indicador"><div className="v">{fmt(r.area_entrada_m2, 2)}</div><div className="r">Área livre de entrada (m²)</div></div>
      </div>
      <Cartao titulo="Critérios avaliados">
        <ul>{Object.entries(r.criterios_m3h || {}).map(([k, v]) => <li key={k}>{k.replace("_", " ")}: {fmt(v as number)} m³/h {k === r.criterio_governante && <Selo tipo="aviso">governante</Selo>}</li>)}</ul>
        <p>Pressurização: <strong>{r.modo_pressao}</strong></p>
      </Cartao>
      <Cartao titulo="Opções de equipamento">
        <table>
          <thead><tr><th>Equipamento</th><th className="num">Qtd</th><th className="num">Q unit. (m³/h)</th><th className="num">Q total</th><th className="num">Potência (kW)</th><th className="num">Custo (R$)</th></tr></thead>
          <tbody>{(r.opcoes_equipamento || []).map((o: any) => (
            <tr key={o.id}><td>{o.nome}</td><td className="num">{o.quantidade}</td><td className="num">{fmt(o.vazao_unitaria_m3h)}</td><td className="num">{fmt(o.vazao_total_m3h)}</td>
              <td className="num">{fmt(o.potencia_total_kw, 2)}</td><td className="num">{fmt(o.custo_total, 2)}</td></tr>
          ))}</tbody>
        </table>
        {(r.rejeitados || []).length > 0 && <p className="nota">Rejeitados: {r.rejeitados.map((x: any) => `${x.nome} (${x.motivo})`).join("; ")}</p>}
      </Cartao>
      {r.sugestao_posicionamento && (
        <Cartao titulo="Sugestão de posicionamento">
          <p>{r.sugestao_posicionamento.observacao}</p>
          <p className="nota">Exaustores em: {r.sugestao_posicionamento.exaustores.map((p: number[]) => `(${fmt(p[0], 1)}; ${fmt(p[1], 1)})`).join(", ")} · Entradas em: {r.sugestao_posicionamento.entradas.map((p: number[]) => `(${fmt(p[0], 1)}; ${fmt(p[1], 1)})`).join(", ")} — visualize na aba Rede/layout.</p>
        </Cartao>
      )}
    </>
  );
}
