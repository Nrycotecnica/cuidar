"""Cotas (alturas) da rede de dutos: de onde saem as descidas e subidas verticais.

A rede é desenhada em planta (x, y). Até a vista 3D, o cálculo tratava todos os
dutos como se estivessem no mesmo plano — a descida da rede principal até cada
captor simplesmente não existia, nem em comprimento nem em curvas. Agora, quando
o projetista informa as cotas, a geometria vertical é deduzida delas aqui, numa
única função, usada pelo cálculo; a vista 3D (frontend/src/lib/cena3d.ts) segue
exatamente as mesmas regras para que o desenho e o cálculo nunca discordem.

Regras (todas as cotas em metros, a partir do piso acabado):
- ``rede["cotas"]["rede_m"]``: cota do eixo da rede principal. Sem ela, nada de
  vertical é considerado e o cálculo fica exatamente como antes.
- ``trecho["cota_m"]``: cota do eixo de um trecho específico (padrão: a da rede).
- ``no["z_m"]``: cota de ligação de captor, filtro, exaustor, descarga ou
  equipamento (boca do captor, bocal do equipamento, topo da chaminé).
- Junções e pontos/curvas ficam na cota do trecho que sai deles (ou, sem saída,
  do primeiro que chega). Assim um trecho que chega numa cota diferente ganha
  uma perna vertical nessa ponta.
- Cada ponta de trecho cuja cota difere da do nó vira uma perna vertical
  (comprimento |Δz|).
"""

from __future__ import annotations

from typing import Any

TIPOS_COM_COTA_PROPRIA = {"captor", "filtro", "exaustor", "descarga", "equipamento"}
TOLERANCIA_M = 0.005  # diferenças menores que 5 mm são arredondamento, não descida


def _numero(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def cota_da_rede(rede: dict[str, Any]) -> float | None:
    return _numero((rede.get("cotas") or {}).get("rede_m"))


def analisar_cotas(rede: dict[str, Any]) -> dict[str, Any] | None:
    """Pernas verticais de cada trecho. ``None`` quando a rede não tem cotas."""
    cota_rede = cota_da_rede(rede)
    if cota_rede is None:
        return None
    nos = {n["id"]: n for n in rede.get("nodes", [])}
    segs = rede.get("segments", [])

    def corrida(s: dict) -> float:
        c = _numero(s.get("cota_m"))
        return cota_rede if c is None else c

    saida: dict[str, dict] = {}
    chegada: dict[str, dict] = {}
    for s in segs:
        saida.setdefault(s["from"], s)
        chegada.setdefault(s["to"], s)

    def cota_no(nid: str) -> float | None:
        n = nos[nid]
        if n.get("type") in TIPOS_COM_COTA_PROPRIA:
            return _numero(n.get("z_m"))
        s = saida.get(nid) or chegada.get(nid)
        return corrida(s) if s else cota_rede

    sem_cota = sorted({nid for s in segs for nid in (s["from"], s["to"])
                       if nos[nid].get("type") in TIPOS_COM_COTA_PROPRIA and cota_no(nid) is None})
    trechos: dict[str, dict] = {}
    for s in segs:
        z = corrida(s)
        pernas = []
        for ponta, nid in (("inicio", s["from"]), ("fim", s["to"])):
            zn = cota_no(nid)
            if zn is None:
                continue
            dz = zn - z
            if abs(dz) > TOLERANCIA_M:
                pernas.append({"no": nid, "ponta": ponta, "cota_no_m": zn, "dz_m": round(dz, 4)})
        trechos[s["id"]] = {
            "cota_m": z,
            "pernas": pernas,
            "vertical_m": round(sum(abs(p["dz_m"]) for p in pernas), 4),
        }
    return {"cota_rede_m": cota_rede, "trechos": trechos, "sem_cota": sem_cota}
