"""Testes de referência do motor de cálculos.

Os valores esperados são obtidos por cálculo independente (fórmulas fechadas
escritas no próprio teste) ou por valores clássicos da literatura (ex.: fator
de atrito em tubo liso).
"""

import math

import pytest

from app.engine import air, friction, units
from app.engine.demo_params import PARAMETROS_DEMO
from app.engine.fans import Curva, ponto_operacao, selecionar_exaustor
from app.engine.hoods import vazao_captor
from app.engine.network import RedeInvalida, analisar_rede
from app.engine.params import ParameterSet
from app.engine.renovacao import dimensionar_renovacao
from app.engine.routing import rotear_rede
from app.engine.seguranca import avaliar
from app.engine.trace import Trace


def ps():
    return ParameterSet.from_list(PARAMETROS_DEMO)


# ---------------------------------------------------------------- unidades / ar
def test_conversoes_exatas():
    assert units.mmh2o_to_pa(1) == pytest.approx(9.80665)
    assert units.cfm_to_m3s(1000) == pytest.approx(0.471947443, rel=1e-9)
    assert units.m3h_to_m3s(3600) == 1.0
    assert units.convert(10, "mmH2O", units.PRESSURE_TO_PA) == pytest.approx(98.0665)
    with pytest.raises(ValueError):
        units.convert(1, "furlong", units.LENGTH_TO_M)


def test_densidade_ar_padrao():
    # 20 °C ao nível do mar: ρ ≈ 1,204 kg/m³
    assert air.densidade(20, 0) == pytest.approx(1.2041, abs=5e-4)
    # altitude reduz a densidade
    assert air.densidade(20, 1000) < air.densidade(20, 0)
    # pressão ISA a 1000 m ≈ 89 875 Pa
    assert air.pressao_atmosferica(1000) == pytest.approx(89875, rel=1e-3)


def test_viscosidade_sutherland():
    assert air.viscosidade_dinamica(20) == pytest.approx(1.81e-5, rel=1e-2)


# ---------------------------------------------------------------- atrito
def test_fator_atrito_laminar():
    assert friction.fator_atrito_colebrook(1000, 0.001) == pytest.approx(0.064)


def test_fator_atrito_tubo_liso_re_1e5():
    # Valor clássico (diagrama de Moody / Colebrook para tubo liso): f ≈ 0,0180
    assert friction.fator_atrito_colebrook(1e5, 0.0) == pytest.approx(0.0180, rel=1e-2)


def test_colebrook_residuo_nulo():
    re, er = 3.2e5, 0.0005
    f = friction.fator_atrito_colebrook(re, er)
    residuo = 1 / math.sqrt(f) + 2 * math.log10(er / 3.7 + 2.51 / (re * math.sqrt(f)))
    assert abs(residuo) < 1e-9


def test_diametro_hidraulico():
    assert friction.diametro_hidraulico_retangular(0.4, 0.2) == pytest.approx(0.26667, rel=1e-4)


# ---------------------------------------------------------------- captores
def test_dalla_valle():
    t = Trace()
    q = vazao_captor({"tipo": "abertura_livre", "processo": "media_dispersao", "distancia_m": 0.3, "area_face_m2": 0.05}, ps(), t, "C1")
    assert q == pytest.approx(1.0 * (10 * 0.09 + 0.05))
    qf = vazao_captor({"tipo": "abertura_flangeada", "processo": "media_dispersao", "distancia_m": 0.3, "area_face_m2": 0.05}, ps(), t, "C1")
    assert qf == pytest.approx(0.75 * 0.95)


def test_coifa_baixa_e_fonte_quente_bloqueia():
    t = Trace()
    q = vazao_captor({"tipo": "coifa_baixa", "processo": "baixa_dispersao", "perimetro_m": 4, "altura_m": 1}, ps(), t, "K1")
    assert q == pytest.approx(1.4 * 4 * 1 * 0.5)
    assert not t.bloqueios
    vazao_captor({"tipo": "coifa_baixa", "processo": "baixa_dispersao", "perimetro_m": 4, "altura_m": 1, "fonte_quente": True}, ps(), t, "K1")
    assert t.bloqueios


def test_parametro_ausente_bloqueia_sem_inventar():
    t = Trace()
    q = vazao_captor({"tipo": "abertura_livre", "processo": "inexistente", "distancia_m": 0.3, "area_face_m2": 0.05}, ps(), t, "C1")
    assert q == 0.0 and any("não cadastrado" in b for b in t.bloqueios)


# ---------------------------------------------------------------- curvas / ponto de operação
CURVA_LINEAR = [{"vazao_m3h": 0, "pressao_pa": 1000}, {"vazao_m3h": 3600 * 2, "pressao_pa": 800}, {"vazao_m3h": 3600 * 4, "pressao_pa": 600}]


def test_interpolacao_sem_extrapolar():
    c = Curva.from_pontos(CURVA_LINEAR)
    assert c.pressao(1.0) == pytest.approx(900)
    assert c.pressao(4.0) == pytest.approx(600)
    assert c.pressao(4.01) is None
    assert c.pressao(-0.1) is None


def test_ponto_operacao_analitico():
    # Ventilador P = 1000 − 100·Q ; sistema P = 50·Q² → 50Q² + 100Q − 1000 = 0 → Q = (−100+√(100²+4·50·1000))/100
    c = Curva.from_pontos(CURVA_LINEAR)
    op = ponto_operacao(c, 50.0)
    q_esp = (-100 + math.sqrt(100**2 + 4 * 50 * 1000)) / (2 * 50)
    assert op["vazao_m3s"] == pytest.approx(q_esp, rel=1e-12)
    assert op["pressao_pa"] == pytest.approx(50 * q_esp**2, rel=1e-9)


def test_ponto_operacao_fora_da_curva():
    c = Curva.from_pontos(CURVA_LINEAR)
    assert ponto_operacao(c, 10000.0) is not None  # interseção perto de Q pequeno
    # sistema muito "leve": interseção acontece além da faixa → None (não extrapola)
    assert ponto_operacao(c, 1.0) is None


def test_selecao_informa_quando_nenhum_atende():
    ex = [{"id": 1, "codigo": "X", "modelo": "pequeno", "curva": CURVA_LINEAR}]
    r = selecionar_exaustor(ex, q_projeto_m3s=10.0, k_total=50, k_estatica=50, rho=1.2, temperatura_c=20, tolerancia_sup=0.2)
    assert r["selecionado"] is None
    assert r["mensagem"] and r["rejeitados"]


def test_selecao_limite_temperatura():
    ex = [{"id": 1, "codigo": "X", "modelo": "m", "curva": CURVA_LINEAR, "temperatura_max_c": 60}]
    r = selecionar_exaustor(ex, 3.0, 50, 50, 1.0, 120, 0.5)
    assert r["selecionado"] is None and "Temperatura" in r["rejeitados"][0]["motivo"]


# ---------------------------------------------------------------- rede
def rede_referencia(diam=None):
    """Rede reta, 1 captor (vazão informada 3600 m³/h), Ø fixo, 10 m até o exaustor,
    descarga reta de 5 m — permite verificação manual."""
    return {
        "nodes": [
            {"id": "c1", "type": "captor", "x": 0, "y": 0, "label": "C1", "captor": {"tipo": "vazao_informada", "vazao_m3h": 3600, "entrada": "flangeada"}},
            {"id": "f", "type": "exaustor", "x": 10, "y": 0},
            {"id": "d", "type": "descarga", "x": 15, "y": 0},
        ],
        "segments": [
            {"id": "s1", "from": "c1", "to": "f", "diametro_mm": diam or 300},
            {"id": "s2", "from": "f", "to": "d", "diametro_mm": diam or 300},
        ],
    }


CFG = {"modulo": "poeira", "contaminante": "poeira_madeira", "temperatura_c": 20, "altitude_m": 0, "diametros_disponiveis_mm": [150, 200, 250, 300, 350, 400, 450, 500]}


def test_rede_caso_referencia_calculo_independente():
    r = analisar_rede(rede_referencia(), CFG, ps())
    rho = air.densidade(20, 0)
    mu = air.viscosidade_dinamica(20)
    d = 0.3
    a = math.pi * d * d / 4
    v = 1.0 / a
    vp = rho * v * v / 2
    re = rho * v * d / mu
    f = friction.fator_atrito_colebrook(re, 0.15e-3 / d)
    succao = f * 10 / d * vp + 0.49 * vp
    descarga = f * 5 / d * vp + 1.0 * vp
    assert r["vazao_total_m3h"] == pytest.approx(3600)
    assert r["pressao_succao_pa"] == pytest.approx(succao, rel=1e-9)
    assert r["pressao_total_ventilador_pa"] == pytest.approx(succao + descarga, rel=1e-9)
    assert r["pressao_estatica_ventilador_pa"] == pytest.approx(succao + descarga - vp, rel=1e-9)
    # velocidade 14,1 m/s < 18 m/s (poeira de madeira) → bloqueio por sedimentação
    assert any("sedimentação" in b for b in r["bloqueios"])


def test_rede_reprodutivel():
    r1 = analisar_rede(rede_referencia(), CFG, ps())
    r2 = analisar_rede(rede_referencia(), CFG, ps())
    assert r1["hash_entradas"] == r2["hash_entradas"]
    assert r1["pressao_total_ventilador_pa"] == r2["pressao_total_ventilador_pa"]


def test_rede_com_cotas_conta_descidas_e_curvas():
    """Rede a 4 m, captor a 1 m e chaminé terminando a 9 m: a sucção ganha 3 m de
    descida e uma curva de 90°; a descarga ganha 5 m de subida e uma curva."""
    rd = rede_referencia()
    rd["cotas"] = {"rede_m": 4.0}
    for n in rd["nodes"]:
        n["z_m"] = {"c1": 1.0, "f": 4.0, "d": 9.0}[n["id"]]
    r = analisar_rede(rd, CFG, ps())
    rho = air.densidade(20, 0)
    d = 0.3
    v = 1.0 / (math.pi * d * d / 4)
    vp = rho * v * v / 2
    f = friction.fator_atrito_colebrook(rho * v * d / air.viscosidade_dinamica(20), 0.15e-3 / d)
    succao = f * 13 / d * vp + (0.49 + 0.39) * vp
    descarga = f * 10 / d * vp + (1.0 + 0.39) * vp
    t = {x["id"]: x for x in r["trechos"]}
    assert t["s1"]["comprimento_m"] == pytest.approx(13)
    assert t["s2"]["comprimento_m"] == pytest.approx(10)
    assert t["s1"]["pernas_verticais"] == [{"no": "c1", "ponta": "inicio", "cota_no_m": 1.0, "dz_m": -3.0}]
    assert r["pressao_succao_pa"] == pytest.approx(succao, rel=1e-9)
    assert r["pressao_total_ventilador_pa"] == pytest.approx(succao + descarga, rel=1e-9)


def test_rede_sem_cotas_fica_como_antes_e_cota_faltando_avisa():
    base = analisar_rede(rede_referencia(), CFG, ps())
    rd = rede_referencia()
    rd["cotas"] = {"rede_m": None}
    assert analisar_rede(rd, CFG, ps())["pressao_total_ventilador_pa"] == base["pressao_total_ventilador_pa"]
    rd["cotas"] = {"rede_m": 4.0}
    rd["nodes"][0]["z_m"] = 1.0  # exaustor e descarga sem cota
    r = analisar_rede(rd, CFG, ps())
    assert {a for a in r["avisos"] if "não informada" in a} == {"Cota do nó f não informada: a descida até ele não entrou no cálculo", "Cota do nó d não informada: a descida até ele não entrou no cálculo"}
    assert {x["id"]: x for x in r["trechos"]}["s2"]["comprimento_m"] == pytest.approx(5)


def rede_dois_ramais():
    return {
        "nodes": [
            {"id": "c1", "type": "captor", "x": 0, "y": 0, "label": "C1", "captor": {"tipo": "vazao_informada", "vazao_m3h": 2000}},
            {"id": "c2", "type": "captor", "x": 5, "y": 4, "label": "C2", "captor": {"tipo": "abertura_flangeada", "processo": "media_dispersao", "distancia_m": 0.2, "area_face_m2": 0.04}},
            {"id": "j", "type": "juncao", "x": 5, "y": 0},
            {"id": "flt", "type": "filtro", "x": 10, "y": 0, "filtro_tipo": "mangas"},
            {"id": "f", "type": "exaustor", "x": 12, "y": 0},
            {"id": "d", "type": "descarga", "x": 12, "y": 6},
        ],
        "segments": [
            {"id": "s1", "from": "c1", "to": "j"},
            {"id": "s2", "from": "c2", "to": "j"},
            {"id": "s3", "from": "j", "to": "flt"},
            {"id": "s4", "from": "flt", "to": "f"},
            {"id": "s5", "from": "f", "to": "d"},
        ],
    }


def test_rede_dois_ramais_continuidade_e_dimensionamento():
    r = analisar_rede(rede_dois_ramais(), CFG, ps())
    t = {x["id"]: x for x in r["trechos"]}
    q2 = 0.75 * 1.0 * (10 * 0.04 + 0.04) * 3600
    assert t["s3"]["vazao_m3h"] == pytest.approx(2000 + q2)
    assert t["s4"]["vazao_m3h"] == pytest.approx(2000 + q2)
    # dimensionado automaticamente com v >= 18 m/s
    for sid in ("s1", "s2", "s3", "s4"):
        assert t[sid]["dimensionado_auto"]
        assert t[sid]["velocidade_ms"] >= 18.0
    # ramal s2 entra a 90° (vem de y=4 para y=0, saída em +x)
    assert any(s["tipo"] == "entrada_ramal" for s in t["s2"]["singulares"])
    assert not any(s["tipo"] == "entrada_ramal" for s in t["s1"]["singulares"])
    # filtro entra na perda de sucção
    assert r["pressao_succao_pa"] > 1200
    assert r["equilibrio"]


def test_rede_invalida():
    rd = rede_dois_ramais()
    rd["nodes"] = [n for n in rd["nodes"] if n["type"] != "exaustor"]
    rd["segments"] = [s for s in rd["segments"] if s["to"] != "f" and s["from"] != "f"]
    with pytest.raises(RedeInvalida):
        analisar_rede(rd, CFG, ps())


def test_estrategias_geram_alternativas_diferentes():
    rd = rede_dois_ramais()
    a = analisar_rede(rd, {**CFG, "estrategia": "menor_perda"}, ps())
    b = analisar_rede(rd, {**CFG, "estrategia": "economica"}, ps())
    assert a["pressao_total_ventilador_pa"] <= b["pressao_total_ventilador_pa"]


# ---------------------------------------------------------------- roteamento
def test_roteamento_desvia_obstaculo():
    capt = [{"id": "c1", "x": 0.0, "y": 0.0}, {"id": "c2", "x": 0.0, "y": 6.0}]
    fan = {"id": "f", "x": 10.0, "y": 3.0}
    obst = [[[4, -1], [6, -1], [6, 7], [4, 7]]]  # parede no meio com passagem acima de y=7
    amb = [[-2, -2], [12, -2], [12, 10], [-2, 10]]
    r = rotear_rede(capt, fan, ambiente=amb, obstaculos=obst, folga=0.2, passo=0.25)
    assert len(r["segments"]) >= 2
    from shapely.geometry import LineString, Polygon
    pol = Polygon(obst[0])
    nos = {"c1": (0, 0), "c2": (0, 6), "f": (10, 3)}
    nos.update({n["id"]: (n["x"], n["y"]) for n in r["nodes"]})
    for s in r["segments"]:
        line = LineString([nos[s["from"]]] + [tuple(p) for p in s["path"]] + [nos[s["to"]]])
        assert not line.intersects(pol)


# ---------------------------------------------------------------- renovação
def test_renovacao():
    ex = [{"id": 1, "codigo": "AX", "modelo": "axial", "curva": [{"vazao_m3h": 0, "pressao_pa": 150}, {"vazao_m3h": 20000, "pressao_pa": 0}], "preco": 1000}]
    r = dimensionar_renovacao({"comprimento_m": 40, "largura_m": 20, "pe_direito_m": 8, "uso": "industrial_geral", "ocupantes": 50, "modo_pressao": "negativa"}, ps(), ex)
    v = 40 * 20 * 8
    assert r["volume_m3"] == v
    assert r["vazao_requerida_m3h"] == pytest.approx(10 * v)
    assert r["vazao_exaustao_m3h"] == pytest.approx(10 * v * 1.1)
    # 50 Pa na curva linear 150→0 Pa: Q = 20000·(100/150)
    qu = 20000 * 100 / 150
    rho = air.densidade(25, 0)
    fr = rho / 1.2
    qu = 20000 * (150 * fr - 50) / (150 * fr)
    assert r["opcoes_equipamento"][0]["vazao_unitaria_m3h"] == pytest.approx(qu, rel=1e-9)
    assert r["opcoes_equipamento"][0]["quantidade"] == math.ceil(10 * v * 1.1 / qu)


# ---------------------------------------------------------------- segurança
def test_seguranca_bloqueia_ate_checklist():
    r = avaliar({"poeira_combustivel": True}, {})
    assert not r["liberado"] and r["pendencias"]
    ck = {f"poeira_combustivel::{i}": {"ok": True} for i in range(len(r["aplicaveis"][0]["itens"]))}
    assert avaliar({"poeira_combustivel": True}, ck)["liberado"]
    assert not avaliar({"controle_fumaca_incendio": True}, {})["liberado"]


def test_poeira_nunca_abaixo_da_velocidade_de_transporte_quando_ha_diametro():
    for e in ("menor_perda", "intermediaria", "economica"):
        r = analisar_rede(rede_dois_ramais(), {**CFG, "estrategia": e}, ps())
        for t in r["trechos"]:
            assert t["velocidade_ms"] >= 18.0 - 1e-9, (e, t["id"])


def test_roteamento_gera_arvore_valida_e_calculavel():
    capt = [{"id": f"c{i}", "x": x, "y": y, "label": f"C{i}", "type": "captor",
             "captor": {"tipo": "vazao_informada", "vazao_m3h": 1500}} for i, (x, y) in enumerate([(2, 2), (2, 8), (8, 8), (8, 2), (5, 5)])]
    fan = {"id": "f", "x": 20.0, "y": 5.0, "type": "exaustor"}
    r = rotear_rede(capt, fan, ambiente=[[0, 0], [22, 0], [22, 10], [0, 10]], folga=0.2, passo=0.25)
    saidas = {}
    for s in r["segments"]:
        assert s["from"] not in saidas, "nó com mais de uma saída"
        saidas[s["from"]] = s
    rede = {"nodes": capt + [fan] + [{**n} for n in r["nodes"]], "segments": r["segments"]}
    res = analisar_rede(rede, {**CFG, "contaminante": "poeira_leve"}, ps())
    assert res["vazao_total_m3h"] == pytest.approx(7500)
