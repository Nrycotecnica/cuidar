"""Roteamento ortogonal de dutos em planta 2D (A* em grade com penalidade de curvas).

Considera: contorno do ambiente, obstáculos (pilares, máquinas) com folga,
regiões bloqueadas pelo usuário, comprimento e número de curvas.
Gera uma árvore: o captor mais distante é ligado ao exaustor (tronco) e os
demais ao ponto mais vantajoso da árvore existente, criando junções.
"""

from __future__ import annotations

import heapq
import math

import numpy as np
import shapely
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]


class RoteamentoFalhou(RuntimeError):
    pass


class Grade:
    def __init__(self, limites, passo, ambiente=None, obstaculos=(), bloqueios=(), folga=0.3, max_celulas=250_000):
        xmin, ymin, xmax, ymax = limites
        area = (xmax - xmin) * (ymax - ymin)
        if area / (passo * passo) > max_celulas:
            passo = math.sqrt(area / max_celulas)
        self.passo = passo
        self.x0, self.y0 = xmin, ymin
        self.nx = max(2, int(math.ceil((xmax - xmin) / passo)) + 1)
        self.ny = max(2, int(math.ceil((ymax - ymin) / passo)) + 1)
        xs = self.x0 + np.arange(self.nx) * passo
        ys = self.y0 + np.arange(self.ny) * passo
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        livre = np.ones((self.nx, self.ny), dtype=bool)
        if ambiente is not None and len(ambiente) >= 3:
            poly = Polygon(ambiente).buffer(-folga)
            if not poly.is_empty:
                livre &= shapely.contains_xy(poly, gx, gy)
        obs = [Polygon(o).buffer(folga) for o in obstaculos if len(o) >= 3]
        obs += [Polygon(b) for b in bloqueios if len(b) >= 3]
        if obs:
            u = unary_union(obs)
            livre &= ~shapely.contains_xy(u, gx, gy)
        self.livre = livre

    def celula(self, x, y):
        i = int(round((x - self.x0) / self.passo))
        j = int(round((y - self.y0) / self.passo))
        return min(max(i, 0), self.nx - 1), min(max(j, 0), self.ny - 1)

    def ponto(self, c):
        return [round(self.x0 + c[0] * self.passo, 4), round(self.y0 + c[1] * self.passo, 4)]

    def liberar_entorno(self, c, raio=2):
        i, j = c
        self.livre[max(0, i - raio): i + raio + 1, max(0, j - raio): j + raio + 1] = True


def _astar(grade: Grade, inicio, alvos: set, alvo_ref, penal_curva: float, proibidas: frozenset = frozenset()):
    """A* com estado (célula, direção). ``alvos``: conjunto de células finais."""
    passo = grade.passo
    tx, ty = alvo_ref

    def h(c):
        if len(alvos) > 1:
            return 0.0
        return (abs(c[0] - tx) + abs(c[1] - ty)) * passo

    abertos = [(h(inicio), 0.0, inicio, -1)]
    custo = {(inicio, -1): 0.0}
    pai = {}
    while abertos:
        f, g, c, d = heapq.heappop(abertos)
        if c in alvos:
            cam = [c]
            k = (c, d)
            while k in pai:
                k = pai[k]
                cam.append(k[0])
            return list(reversed(cam)), g
        if g > custo.get((c, d), math.inf) + 1e-12:
            continue
        for nd, (dx, dy) in enumerate(DIRS):
            n = (c[0] + dx, c[1] + dy)
            if not (0 <= n[0] < grade.nx and 0 <= n[1] < grade.ny):
                continue
            if (not grade.livre[n] and n not in alvos) or (n in proibidas and n not in alvos):
                continue
            ng = g + passo + (penal_curva if (d != -1 and nd != d) else 0.0)
            if (d != -1 and nd == (d + 2) % 4):
                continue
            if ng < custo.get((n, nd), math.inf) - 1e-12:
                custo[(n, nd)] = ng
                pai[(n, nd)] = (c, d)
                heapq.heappush(abertos, (ng + h(n), ng, n, nd))
    return None, math.inf


def simplificar(cels):
    """Mantém apenas os vértices de mudança de direção."""
    if len(cels) <= 2:
        return list(cels)
    out = [cels[0]]
    for i in range(1, len(cels) - 1):
        d1 = (cels[i][0] - cels[i - 1][0], cels[i][1] - cels[i - 1][1])
        d2 = (cels[i + 1][0] - cels[i][0], cels[i + 1][1] - cels[i][1])
        if d1 != d2:
            out.append(cels[i])
    out.append(cels[-1])
    return out


def rotear_rede(captores: list[dict], exaustor: dict, ambiente=None, obstaculos=(), bloqueios=(),
                folga=0.3, passo=0.25, penal_curva=2.0, margem=2.0) -> dict:
    """Gera nós e trechos de uma rede em árvore ligando captores ao exaustor.

    captores: [{"id","x","y","label"}]; exaustor: {"id","x","y"}.
    Retorna {"nodes": [...junções...], "segments": [...], "comprimento_total_m", "avisos"}.
    """
    pts = [(c["x"], c["y"]) for c in captores] + [(exaustor["x"], exaustor["y"])]
    if ambiente:
        pts += [tuple(p) for p in ambiente]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    limites = (min(xs) - margem, min(ys) - margem, max(xs) + margem, max(ys) + margem)
    grade = Grade(limites, passo, ambiente, obstaculos, bloqueios, folga)
    avisos = []
    if grade.passo != passo:
        avisos.append(f"Passo da grade ampliado para {grade.passo:.2f} m devido ao tamanho da área.")

    fan_c = grade.celula(exaustor["x"], exaustor["y"])
    grade.liberar_entorno(fan_c)
    proximo: dict = {}  # célula -> próxima célula rumo ao exaustor
    arvore = {fan_c}
    juncoes: set = set()
    origem_captor: dict = {}

    celulas_captores = {grade.celula(c["x"], c["y"]) for c in captores}
    ordem = sorted(captores, key=lambda c: -math.dist((c["x"], c["y"]), (exaustor["x"], exaustor["y"])))
    for idx, c in enumerate(ordem):
        cc = grade.celula(c["x"], c["y"])
        grade.liberar_entorno(cc)
        if cc in arvore or cc in origem_captor:
            avisos.append(f"Captor {c.get('label') or c['id']} coincide com a rede existente; deslocar o captor.")
            continue
        alvos = (arvore - set(origem_captor)) if idx else {fan_c}
        cam, _ = _astar(grade, cc, alvos, fan_c, penal_curva, frozenset(celulas_captores - {cc}))
        if cam is None:
            raise RoteamentoFalhou(f"Não foi possível rotear o captor {c.get('label') or c['id']} até a rede (obstáculos/bloqueios fecham a passagem)")
        destino = cam[-1]
        if destino != fan_c:
            juncoes.add(destino)
        for a, b in zip(cam, cam[1:]):
            proximo[a] = b
        arvore.update(cam)
        origem_captor[cc] = c

    # Montagem dos nós e trechos
    nos_extra = []
    ids_juncao = {}
    for k, j in enumerate(sorted(juncoes)):
        jid = f"J{k+1}"
        ids_juncao[j] = jid
        x, y = grade.ponto(j)
        nos_extra.append({"id": jid, "type": "juncao", "x": x, "y": y, "label": jid})

    def id_no(cel):
        if cel == fan_c:
            return exaustor["id"]
        if cel in ids_juncao:
            return ids_juncao[cel]
        return origem_captor[cel]["id"]

    segmentos = []
    inicios = list(origem_captor.keys()) + list(ids_juncao.keys())
    total = 0.0
    for k, ini in enumerate(inicios):
        cam = [ini]
        cur = ini
        while True:
            cur = proximo[cur]
            cam.append(cur)
            if cur == fan_c or cur in ids_juncao:
                break
        simp = simplificar(cam)
        path = [grade.ponto(p) for p in simp]
        # pontas exatas nos nós originais
        if ini in origem_captor:
            path[0] = [origem_captor[ini]["x"], origem_captor[ini]["y"]]
        if cur == fan_c:
            path[-1] = [exaustor["x"], exaustor["y"]]
        comp = sum(math.dist(path[i - 1], path[i]) for i in range(1, len(path)))
        total += comp
        segmentos.append({
            "id": f"R{k+1}", "from": id_no(ini), "to": id_no(cur),
            "path": path[1:-1], "label": f"R{k+1}", "roteado": True,
        })
    # extremidades com pequenos desvios (ponto exato x grade) geram vértices quase colineares — aceitável
    return {"nodes": nos_extra, "segments": segmentos, "comprimento_total_m": total, "avisos": avisos,
            "passo_grade_m": grade.passo}
