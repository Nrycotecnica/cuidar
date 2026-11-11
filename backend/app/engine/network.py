"""Análise de redes de dutos em árvore (exaustão por sucção até o exaustor e
descarga após ele).

Método: contabilidade de pressão total (TP) por trecho — perdas por atrito
(Darcy-Weisbach/Colebrook) e perdas singulares (K·VP) — com determinação do
ramo governante, verificação de equilíbrio nas junções e cálculo das pressões
total e estática do ventilador:

    FTP = TP_saída − TP_entrada
    FSP = FTP − VP_saída_ventilador
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from . import ENGINE_VERSION
from .air import area_circular, densidade, pressao_dinamica, viscosidade_dinamica
from .friction import diametro_hidraulico_retangular, fator_atrito_colebrook, perda_atrito, reynolds
from .geometry import angulo_entre, angulos_internos, comprimento_polilinha, direcao, limpar
from .hoods import vazao_captor
from .params import ParameterSet, ParametroAusente
from .trace import Trace, fmt, hash_entradas

TIPOS_NO = {"captor", "juncao", "ponto", "filtro", "exaustor", "descarga", "equipamento"}
MODULOS = {"poeira", "fumos", "renovacao"}
ESTRATEGIAS = {"menor_perda", "intermediaria", "economica"}


class RedeInvalida(ValueError):
    pass


def _k_curva(params: ParameterSet, angulo: float) -> float:
    """K de curva proporcional ao ângulo a partir do K da curva de 90°."""
    k90 = float(params.get("k_curva_90"))
    return k90 * min(angulo, 180.0) / 90.0


def _k_entrada_ramal(params: ParameterSet, angulo: float) -> float:
    """Interpolação linear entre os K cadastrados para 30°, 45° e 90°."""
    tab = sorted((a, float(params.get(f"k_entrada_ramal_{a}"))) for a in (30, 45, 90))
    if angulo <= tab[0][0]:
        return tab[0][1]
    for (a0, k0), (a1, k1) in zip(tab, tab[1:]):
        if angulo <= a1:
            return k0 + (k1 - k0) * (angulo - a0) / (a1 - a0)
    return tab[-1][1]


def _faixa_velocidade(modulo: str, contaminante: str | None, params: ParameterSet, trace: Trace) -> tuple[float | None, float | None]:
    if modulo == "poeira":
        if not contaminante:
            trace.bloqueio("Contaminante não informado: a velocidade mínima de transporte não pode ser definida")
            return None, None
        ch = f"vel_transporte_min.{contaminante}"
        if not params.tem(ch):
            trace.bloqueio(f"Parâmetro {ch} não cadastrado")
            return None, None
        vmin = float(params.get(ch))
        vmax = params.get_opcional("vel_duto_max.poeira")
        return vmin, (float(vmax) if vmax is not None else None)
    vmin = params.get_opcional(f"vel_duto_min.{modulo}")
    vmax = params.get_opcional(f"vel_duto_max.{modulo}")
    if vmin is None or vmax is None:
        trace.bloqueio(f"Faixa de velocidade em dutos para '{modulo}' não cadastrada (vel_duto_min/max.{modulo})")
    return (float(vmin) if vmin is not None else None, float(vmax) if vmax is not None else None)


def _escolher_diametro(q: float, diametros_mm: list[float], vmin, vmax, estrategia: str, modulo: str, trace: Trace, rotulo: str) -> float:
    ds = sorted(diametros_mm)
    vel = {d: q / area_circular(d / 1000.0) for d in ds}
    ok_min = [d for d in ds if vmin is None or vel[d] >= vmin - 1e-9]
    ok_max = [d for d in ds if vmax is None or vel[d] <= vmax + 1e-9]
    faixa = [d for d in ds if d in ok_min and d in ok_max]
    if estrategia == "menor_perda" or (estrategia != "menor_perda" and vmax is None):
        if estrategia != "menor_perda" and vmax is None:
            trace.aviso(f"Estratégia '{estrategia}' requer velocidade máxima cadastrada; usado critério de menor perda.")
        if ok_min:
            return max(ok_min)
    elif estrategia == "economica":
        if faixa:
            return min(faixa)
        if ok_max and modulo != "poeira":
            return min(ok_max)
    elif estrategia == "intermediaria":
        if faixa and vmin is not None:
            alvo = (vmin + vmax) / 2.0
            return min(faixa, key=lambda d: (abs(vel[d] - alvo), d))
    if not ok_min:
        trace.aviso(f"{rotulo}: nenhum diâmetro disponível atinge a velocidade mínima; adotado o menor diâmetro ({fmt(ds[0], 0)} mm).")
        return ds[0]
    return max(ok_min)


def analisar_rede(rede: dict[str, Any], config: dict[str, Any], params: ParameterSet) -> dict[str, Any]:
    """Analisa a rede e retorna resultados completos e auditáveis."""
    trace = Trace()
    entradas = {"rede": rede, "config": config, "parametros": {k: (p.valor, p.status) for k, p in params.itens.items()}}
    modulo = config.get("modulo", "poeira")
    if modulo not in MODULOS:
        raise RedeInvalida(f"Módulo inválido: {modulo}")
    estrategia = config.get("estrategia", "menor_perda")
    if estrategia not in ESTRATEGIAS:
        raise RedeInvalida(f"Estratégia inválida: {estrategia}")

    nos = {n["id"]: n for n in rede.get("nodes", [])}
    if len(nos) != len(rede.get("nodes", [])):
        raise RedeInvalida("IDs de nós repetidos")
    segs = {s["id"]: s for s in rede.get("segments", [])}
    for s in segs.values():
        if s["from"] not in nos or s["to"] not in nos:
            raise RedeInvalida(f"Trecho {s['id']} referencia nó inexistente")
        if s["from"] == s["to"]:
            raise RedeInvalida(f"Trecho {s['id']} liga um nó a ele mesmo")
    for n in nos.values():
        if n.get("type") not in TIPOS_NO:
            raise RedeInvalida(f"Tipo de nó inválido em {n['id']}: {n.get('type')}")

    exaustores = [n for n in nos.values() if n["type"] == "exaustor"]
    if len(exaustores) != 1:
        raise RedeInvalida("A rede deve conter exatamente um nó do tipo 'exaustor'")
    fan = exaustores[0]["id"]

    saidas: dict[str, list[str]] = defaultdict(list)
    entradas_no: dict[str, list[str]] = defaultdict(list)
    for s in segs.values():
        saidas[s["from"]].append(s["id"])
        entradas_no[s["to"]].append(s["id"])
    for nid, outs in saidas.items():
        if len(outs) > 1:
            raise RedeInvalida(f"O nó {nos[nid].get('label') or nid} possui mais de um trecho de saída (rede deve ser em árvore no sentido do escoamento)")

    # Classificação: sucção (chega ao exaustor) e descarga (sai do exaustor)
    def caminho_ate_fim(nid):
        visit = []
        cur = nid
        guard = 0
        while saidas.get(cur):
            sid = saidas[cur][0]
            visit.append(sid)
            cur = segs[sid]["to"]
            guard += 1
            if guard > 10000:
                raise RedeInvalida("Ciclo detectado na rede")
        return visit, cur

    lado: dict[str, str] = {}
    cur, guard = fan, 0
    while saidas.get(cur):
        sid = saidas[cur][0]
        lado[sid] = "descarga"
        cur = segs[sid]["to"]
        guard += 1
        if guard > 10000:
            raise RedeInvalida("Ciclo detectado na rede")
    for sid in segs:
        if sid in lado:
            continue
        cam, fim = caminho_ate_fim(segs[sid]["from"])
        if not any(segs[x]["to"] == fan for x in cam):
            raise RedeInvalida(f"Trecho {segs[sid].get('label') or sid} não está conectado ao exaustor")
        lado[sid] = "succao"

    captores = [n for n in nos.values() if n["type"] == "captor"]
    if not captores:
        raise RedeInvalida("A rede não possui captores")
    for c in captores:
        if entradas_no.get(c["id"]):
            raise RedeInvalida(f"Captor {c.get('label') or c['id']} não pode receber trechos")

    # Propriedades do ar
    t_c = float(config.get("temperatura_c", 20.0))
    alt = float(config.get("altitude_m", 0.0))
    rho = densidade(t_c, alt)
    mu = viscosidade_dinamica(t_c)
    trace.add("Densidade do ar", "ρ = p_atm(h)/(R·T)", f"T = {fmt(t_c,1)} °C; h = {fmt(alt,0)} m", round(rho, 5), "kg/m³", "Gás ideal, atmosfera padrão ISA")
    trace.add("Viscosidade dinâmica do ar", "μ = 1,458e-6·T^1,5/(T+110,4)", f"T = {fmt(t_c+273.15,2)} K", mu, "Pa·s", "Lei de Sutherland")
    trace.hipotese("Ar seco tratado como gás ideal; umidade e carga de particulado não alteram a densidade.")
    trace.hipotese("Escoamento incompressível e permanente; perdas proporcionais a Q² para a curva do sistema.")

    # Vazões nos captores
    q_no: dict[str, float] = {}
    for c in captores:
        rot = c.get("label") or c["id"]
        q_no[c["id"]] = vazao_captor(c.get("captor") or {}, params, trace, rot)

    # Propagação de vazões (continuidade) — ordenação topológica
    q_seg: dict[str, float] = {}
    pendentes = dict.fromkeys(segs)
    progresso = True
    while pendentes and progresso:
        progresso = False
        for sid in list(pendentes):
            orig = segs[sid]["from"]
            if all(e in q_seg for e in entradas_no.get(orig, [])):
                q_seg[sid] = q_no.get(orig, 0.0) + sum(q_seg[e] for e in entradas_no.get(orig, []))
                del pendentes[sid]
                progresso = True
    if pendentes:
        raise RedeInvalida("Não foi possível propagar as vazões (ciclo ou nó desconectado)")
    q_total = sum(q_seg[e] for e in entradas_no.get(fan, []))
    trace.add("Vazão total no exaustor (continuidade)", "Q_exaustor = Σ Q_captores", " + ".join(fmt(q_no[c['id']]*3600, 0) for c in captores) + " m³/h", round(q_total * 3600, 2), "m³/h")

    vmin, vmax = _faixa_velocidade(modulo, config.get("contaminante"), params, trace)
    diametros = config.get("diametros_disponiveis_mm") or []
    if not diametros:
        trace.bloqueio("Nenhum diâmetro de duto disponível no catálogo")
        diametros = []

    # Geometria e dimensionamento de cada trecho
    material_padrao = config.get("material_padrao", "galvanizado")
    res_seg: dict[str, dict] = {}
    pts_seg: dict[str, list] = {}
    for sid, s in segs.items():
        a, b = nos[s["from"]], nos[s["to"]]
        pts = s.get("path") or []
        pts = [[a["x"], a["y"]]] + [p for p in pts] + [[b["x"], b["y"]]]
        pts = limpar(pts)
        pts_seg[sid] = pts
        rot = s.get("label") or sid
        q = q_seg[sid]
        forma = s.get("forma", "circular")
        auto = False
        if forma == "retangular":
            w, h = s.get("largura_mm"), s.get("altura_mm")
            if not w or not h:
                trace.bloqueio(f"{rot}: duto retangular requer largura e altura")
                w = h = 100.0
            area = (w / 1000) * (h / 1000)
            dh = diametro_hidraulico_retangular(w / 1000, h / 1000)
            d_mm = None
        else:
            d_mm = s.get("diametro_mm")
            if not d_mm:
                if q > 0 and diametros:
                    d_mm = _escolher_diametro(q, diametros, vmin, vmax, estrategia, modulo, trace, rot)
                    auto = True
                else:
                    d_mm = 100.0
            area = area_circular(d_mm / 1000.0)
            dh = d_mm / 1000.0
        v = q / area if area > 0 else 0.0
        vp = pressao_dinamica(rho, v)
        mat = s.get("material") or material_padrao
        try:
            eps_mm = float(params.get(f"rugosidade.{mat}"))
        except ParametroAusente:
            trace.bloqueio(f"{rot}: rugosidade do material '{mat}' não cadastrada")
            eps_mm = 0.0
        L = comprimento_polilinha(pts) + float(s.get("comprimento_extra_m") or 0.0)
        if v > 0:
            re = reynolds(rho, v, dh, mu)
            f = fator_atrito_colebrook(re, eps_mm / 1000.0 / dh)
        else:
            re, f = 0.0, 0.0
        dp_atr = perda_atrito(f, L, dh, vp) if v > 0 else 0.0
        if lado[sid] == "succao" and modulo == "poeira" and vmin is not None and v < vmin - 1e-9:
            trace.bloqueio(f"{rot}: velocidade {fmt(v,2)} m/s abaixo da velocidade mínima de transporte ({fmt(vmin,1)} m/s) — risco de sedimentação")
        if vmax is not None and v > vmax + 1e-9:
            trace.aviso(f"{rot}: velocidade {fmt(v,2)} m/s acima da máxima recomendada ({fmt(vmax,1)} m/s) — ruído/abrasão/perda elevada")
        res_seg[sid] = {
            "id": sid, "label": rot, "de": s["from"], "para": s["to"], "lado": lado[sid],
            "vazao_m3s": q, "vazao_m3h": q * 3600, "forma": forma, "diametro_mm": d_mm,
            "largura_mm": s.get("largura_mm"), "altura_mm": s.get("altura_mm"),
            "dimensionado_auto": auto, "material": mat, "area_m2": area, "dh_m": dh,
            "velocidade_ms": v, "vp_pa": vp, "reynolds": re, "fator_atrito": f,
            "rugosidade_mm": eps_mm, "comprimento_m": L, "perda_atrito_pa": dp_atr,
            "singulares": [], "curvas": [], "path": pts,
        }
        trace.add(
            f"{rot}: velocidade e pressão dinâmica",
            "v = Q/A; VP = ρ·v²/2",
            f"Q = {fmt(q,4)} m³/s; A = {fmt(area,5)} m² (" + (f"Ø{fmt(d_mm,0)} mm" if d_mm else f"{s.get('largura_mm')}x{s.get('altura_mm')} mm") + ")",
            round(v, 3), f"m/s (VP = {fmt(vp,1)} Pa)",
        )
        if v > 0:
            trace.add(
                f"{rot}: perda por atrito",
                "ΔP = f·(L/D)·VP; f por Colebrook-White",
                f"Re = {fmt(re,0)}; ε = {fmt(eps_mm,3)} mm; f = {fmt(f,5)}; L = {fmt(L,2)} m",
                round(dp_atr, 2), "Pa",
            )

    def add_k(sid, tipo, k, descr):
        r = res_seg[sid]
        r["singulares"].append({"tipo": tipo, "k": k, "descricao": descr})

    # Curvas internas aos trechos
    for sid, pts in pts_seg.items():
        for ang in angulos_internos(pts):
            k = _k_curva(params, ang)
            add_k(sid, "curva", k, f"Curva {fmt(ang,0)}°")
            res_seg[sid]["curvas"].append(round(ang, 1))
        for c in segs[sid].get("curvas_extra") or []:
            for _ in range(int(c.get("qtd", 1))):
                ang = float(c.get("angulo", 90))
                add_k(sid, "curva", _k_curva(params, ang), f"Curva {fmt(ang,0)}° (vertical/extra)")
                res_seg[sid]["curvas"].append(ang)
        for extra in segs[sid].get("singulares_extra") or []:
            add_k(sid, "outro", float(extra["k"]), extra.get("descricao", "Singularidade informada"))
            trace.hipotese("Coeficientes K informados manualmente em trechos devem ter referência registrada.")

    # Mudanças de direção e de seção em nós de passagem
    for nid, n in nos.items():
        ins, outs = entradas_no.get(nid, []), saidas.get(nid, [])
        if not outs:
            continue
        so = outs[0]
        if len(ins) == 1 and n["type"] in ("ponto", "filtro", "equipamento"):
            si = ins[0]
            d1 = direcao(pts_seg[si][-2], pts_seg[si][-1])
            d2 = direcao(pts_seg[so][0], pts_seg[so][1])
            if d1 and d2 and n["type"] == "ponto":
                ang = angulo_entre(d1, d2)
                if ang > 1.0:
                    add_k(so, "curva", _k_curva(params, ang), f"Curva {fmt(ang,0)}° no nó {n.get('label') or nid}")
                    res_seg[so]["curvas"].append(round(ang, 1))
        if n["type"] == "juncao":
            if len(ins) < 2:
                trace.aviso(f"Junção {n.get('label') or nid} com menos de dois ramais de entrada")
            d_out = direcao(pts_seg[so][0], pts_seg[so][1])
            # tronco = ramal mais alinhado com a saída
            def desvio(si):
                d_in = direcao(pts_seg[si][-2], pts_seg[si][-1])
                return angulo_entre(d_in, d_out) if (d_in and d_out) else 90.0
            ordenados = sorted(ins, key=lambda si: (desvio(si), -q_seg[si]))
            for si in ordenados[1:]:
                ang = segs[si].get("angulo_entrada_deg") or desvio(si)
                k = _k_entrada_ramal(params, float(ang))
                add_k(si, "entrada_ramal", k, f"Entrada de ramal {fmt(float(ang),0)}° na junção {n.get('label') or nid}")
            if ordenados:
                res_seg[ordenados[0]]["tronco_em"] = nid
        # transição de seção (redução/expansão)
        for si in ins:
            if n["type"] in ("ponto", "juncao") and res_seg[si]["area_m2"] and abs(res_seg[si]["area_m2"] - res_seg[so]["area_m2"]) / res_seg[so]["area_m2"] > 0.02:
                if n["type"] == "juncao" and res_seg[si].get("tronco_em") != nid:
                    continue
                k = float(params.get("k_transicao"))
                vp_max = max(res_seg[si]["vp_pa"], res_seg[so]["vp_pa"])
                # aplicado ao trecho de saída, referenciado à maior VP
                fator = vp_max / res_seg[so]["vp_pa"] if res_seg[so]["vp_pa"] > 0 else 0
                add_k(so, "transicao", k * fator, f"Transição de seção no nó {n.get('label') or nid} (K={fmt(k,2)} sobre a maior VP)")

    # Entrada no captor
    for c in captores:
        so = saidas.get(c["id"], [None])[0]
        if not so:
            raise RedeInvalida(f"Captor {c.get('label') or c['id']} sem trecho de saída")
        tipo_ent = (c.get("captor") or {}).get("entrada", "flangeada")
        ch = f"k_entrada_captor.{tipo_ent}"
        try:
            k = float(params.get(ch))
            add_k(so, "entrada_captor", k, f"Perda de entrada do captor ({tipo_ent})")
        except ParametroAusente:
            trace.bloqueio(f"Coeficiente {ch} não cadastrado")

    # Saída livre na descarga
    descargas = [n for n in nos.values() if n["type"] == "descarga"]
    for d in descargas:
        for si in entradas_no.get(d["id"], []):
            k = float(params.get("k_saida"))
            add_k(si, "saida", k, "Perda de saída (energia cinética descarregada)")

    # Perdas singulares e totais por trecho
    for sid, r in res_seg.items():
        ksum = sum(x["k"] for x in r["singulares"])
        r["k_total"] = ksum
        r["perda_singular_pa"] = ksum * r["vp_pa"]
        r["perda_total_pa"] = r["perda_atrito_pa"] + r["perda_singular_pa"]
        if r["singulares"]:
            trace.add(
                f"{r['label']}: perdas singulares",
                "ΔP = ΣK·VP",
                " + ".join(f"{x['descricao']} K={fmt(x['k'],3)}" for x in r["singulares"]) + f"; VP = {fmt(r['vp_pa'],1)} Pa",
                round(r["perda_singular_pa"], 2), "Pa",
            )

    # Perdas concentradas em nós (filtros/equipamentos)
    perda_no: dict[str, float] = {}
    for nid, n in nos.items():
        if n["type"] in ("filtro", "equipamento"):
            if n.get("perda_pa") is not None:
                dp = float(n["perda_pa"])
                trace.hipotese("Perdas em filtros/equipamentos informadas no nó devem vir da folha de dados do equipamento.")
                origem = "informada"
            else:
                tipo = n.get("filtro_tipo") or n.get("equipamento_tipo") or "generico"
                try:
                    dp = float(params.get(f"dp_filtro.{tipo}"))
                    origem = f"parâmetro dp_filtro.{tipo}"
                except ParametroAusente:
                    trace.bloqueio(f"Perda de carga do {n['type']} '{n.get('label') or nid}' não informada e parâmetro dp_filtro.{tipo} não cadastrado")
                    dp = 0.0
                    origem = "ausente"
            perda_no[nid] = dp
            trace.add(f"{n.get('label') or nid}: perda no {n['type']}", "ΔP = valor de projeto", origem, round(dp, 1), "Pa")
            if n["type"] == "filtro":
                trace.hipotese("Perda do filtro considerada na condição de projeto (saturação/limpeza devem ser verificadas).")

    # Perda acumulada por caminho (captor → exaustor)
    perda_ate_fan: dict[str, float] = {}
    caminhos: dict[str, list[str]] = {}
    for c in captores:
        total = 0.0
        cur = c["id"]
        cam = []
        while cur != fan:
            if not saidas.get(cur):
                raise RedeInvalida(f"Caminho do captor {c.get('label') or c['id']} não chega ao exaustor")
            sid = saidas[cur][0]
            total += res_seg[sid]["perda_total_pa"]
            cam.append(sid)
            cur = segs[sid]["to"]
            if cur != fan:
                total += perda_no.get(cur, 0.0)
        perda_ate_fan[c["id"]] = total
        caminhos[c["id"]] = cam

    gov = max(perda_ate_fan, key=perda_ate_fan.get)
    tp_succao = perda_ate_fan[gov]
    trace.add(
        "Perda no ramo governante (sucção)",
        "ΔP_sucção = max(Σ perdas captor→exaustor)",
        f"Ramo governante: {nos[gov].get('label') or gov}",
        round(tp_succao, 2), "Pa",
    )

    # Equilíbrio nas junções
    limite = float(params.get("desequilibrio_max"))
    equilibrio = []
    def perda_montante(sid):
        """Maior perda acumulada de qualquer captor até o fim do trecho sid."""
        orig = segs[sid]["from"]
        base = res_seg[sid]["perda_total_pa"]
        if nos[orig]["type"] == "captor":
            return base
        ins = entradas_no.get(orig, [])
        return base + perda_no.get(orig, 0.0) + (max(perda_montante(x) for x in ins) if ins else 0.0)

    for nid, n in nos.items():
        ins = entradas_no.get(nid, [])
        if n["type"] == "juncao" and len(ins) >= 2:
            pm = {si: perda_montante(si) for si in ins}
            alto = max(pm.values())
            for si, p in pm.items():
                if p >= alto - 1e-9 or p <= 0:
                    continue
                razao = alto / p
                item = {
                    "juncao": n.get("label") or nid, "trecho": res_seg[si]["label"],
                    "perda_ramal_pa": p, "perda_governante_pa": alto, "razao": razao,
                }
                if razao <= limite:
                    qc = res_seg[si]["vazao_m3s"] * math.sqrt(razao)
                    item["situacao"] = "aceitavel"
                    item["vazao_corrigida_m3h"] = qc * 3600
                    item["mensagem"] = (
                        f"Razão {fmt(razao,2)} ≤ {fmt(limite,2)}: o ramal tende a operar com ≈{fmt(qc*3600,0)} m³/h "
                        "(Q·√(P_gov/P_ramal)); considerar no balanço final."
                    )
                else:
                    item["situacao"] = "desequilibrado"
                    item["mensagem"] = (
                        f"Razão {fmt(razao,2)} > {fmt(limite,2)}: redimensionar o ramal (reduzir diâmetro) ou prever registro de balanceamento."
                    )
                    trace.aviso(f"Desequilíbrio na junção {item['juncao']} (ramal {item['trecho']}): razão {fmt(razao,2)}")
                equilibrio.append(item)

    # Descarga
    segs_desc = [sid for sid in segs if lado[sid] == "descarga"]
    tp_descarga = sum(res_seg[s]["perda_total_pa"] for s in segs_desc) + sum(
        perda_no.get(segs[s]["to"], 0.0) for s in segs_desc
    )
    saida_fan = saidas.get(fan, [None])[0]
    entrada_fan = max(entradas_no.get(fan, []), key=lambda s: q_seg[s]) if entradas_no.get(fan) else None
    if saida_fan:
        vp_saida = res_seg[saida_fan]["vp_pa"]
    else:
        vp_saida = res_seg[entrada_fan]["vp_pa"] if entrada_fan else 0.0
        tp_descarga += vp_saida * float(params.get("k_saida"))
        trace.hipotese("Sem trechos de descarga: considerada descarga livre na boca do exaustor com VP igual à do duto de entrada.")
    if len(entradas_no.get(fan, [])) > 1:
        trace.aviso("Mais de um trecho chegando ao exaustor: recomenda-se uma junção antes da boca de aspiração.")

    ftp = tp_succao + tp_descarga
    fsp = ftp - vp_saida
    trace.add("Pressão total do ventilador", "FTP = ΔP_sucção + ΔP_descarga", f"{fmt(tp_succao,1)} + {fmt(tp_descarga,1)}", round(ftp, 2), "Pa")
    trace.add("Pressão estática do ventilador", "FSP = FTP − VP_saída", f"{fmt(ftp,1)} − {fmt(vp_saida,1)}", round(fsp, 2), "Pa")
    k_total = ftp / q_total**2 if q_total > 0 else 0.0
    k_est = fsp / q_total**2 if q_total > 0 else 0.0
    trace.add("Curva do sistema", "ΔP_sis(Q) = k·Q²", f"k_total = {fmt(k_total,3)}; k_estática = {fmt(k_est,3)} Pa/(m³/s)²", round(k_total, 4), "Pa·s²/m⁶")

    # Quantitativos geométricos
    resumo_dutos: dict[str, float] = defaultdict(float)
    for r in res_seg.values():
        chave = f"Ø{int(r['diametro_mm'])}" if r["diametro_mm"] else f"{r['largura_mm']}x{r['altura_mm']}"
        resumo_dutos[f"{chave}|{r['material']}"] += r["comprimento_m"]

    potencia_ar_w = q_total * ftp
    trace.add("Potência transmitida ao ar", "P_ar = Q·FTP", f"{fmt(q_total,4)}·{fmt(ftp,1)}", round(potencia_ar_w / 1000, 4), "kW")

    nao_aprov = params.nao_aprovados()
    if nao_aprov:
        trace.aviso(f"{len(nao_aprov)} parâmetro(s) técnico(s) utilizado(s) ainda sem aprovação: " + ", ".join(nao_aprov))

    return {
        "versao_motor": ENGINE_VERSION,
        "hash_entradas": hash_entradas(entradas),
        "modulo": modulo,
        "estrategia": estrategia,
        "ar": {"temperatura_c": t_c, "altitude_m": alt, "densidade": rho, "viscosidade": mu},
        "faixa_velocidade": {"min": vmin, "max": vmax},
        "vazao_total_m3s": q_total,
        "vazao_total_m3h": q_total * 3600,
        "captores": [
            {"id": c["id"], "label": c.get("label") or c["id"], "vazao_m3h": q_no[c["id"]] * 3600,
             "perda_ate_exaustor_pa": perda_ate_fan[c["id"]], "governante": c["id"] == gov,
             "caminho": caminhos[c["id"]]}
            for c in captores
        ],
        "trechos": list(res_seg.values()),
        "perdas_nos": [{"id": k, "label": nos[k].get("label") or k, "perda_pa": v} for k, v in perda_no.items()],
        "equilibrio": equilibrio,
        "pressao_succao_pa": tp_succao,
        "pressao_descarga_pa": tp_descarga,
        "vp_saida_pa": vp_saida,
        "pressao_total_ventilador_pa": ftp,
        "pressao_estatica_ventilador_pa": fsp,
        "k_sistema_total": k_total,
        "k_sistema_estatica": k_est,
        "potencia_ar_kw": potencia_ar_w / 1000,
        "resumo_dutos_m": dict(resumo_dutos),
        "parametros_usados": params.relatorio_usados(),
        "parametros_nao_aprovados": nao_aprov,
        **trace.as_dict(),
    }
