"""Carga inicial: administrador, parâmetros e catálogo DEMONSTRATIVOS (fictícios)."""

from __future__ import annotations

import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .engine.demo_params import PARAMETROS_DEMO
from .models import Cliente, ComponenteDuto, Exaustor, ParametroTecnico, Projeto, Rede, Usuario, Versao
from .security import hash_senha

AVISO = "DEMONSTRATIVO — dados fictícios para testes do software"


def _curva(pts):
    return [{"vazao_m3h": q, "pressao_pa": p, "potencia_kw": w} for q, p, w in pts]


EXAUSTORES_DEMO = [
    ("DEMO-RA-300", "Radial pás retas 300 (FICTÍCIO)", "centrifugo_radial", 3500, 4.0, 120,
     _curva([(800, 2900, 1.6), (1500, 2850, 2.0), (2500, 2700, 2.6), (3500, 2450, 3.1), (4500, 2050, 3.5), (5200, 1650, 3.7)]), 18500),
    ("DEMO-RA-400", "Radial pás retas 400 (FICTÍCIO)", "centrifugo_radial", 1750, 7.5, 120,
     _curva([(2000, 3300, 3.4), (3500, 3250, 4.3), (5000, 3100, 5.2), (6500, 2800, 6.0), (8000, 2350, 6.6), (9000, 1950, 6.9)]), 26800),
    ("DEMO-RA-450", "Radial pás retas 450 (FICTÍCIO)", "centrifugo_radial", 1750, 15.0, 120,
     _curva([(3000, 4300, 6.0), (5000, 4250, 7.6), (7000, 4050, 9.1), (9000, 3650, 10.4), (11000, 3000, 11.4)]), 34500),
    ("DEMO-LL-450", "Limit-load 450 (FICTÍCIO)", "centrifugo_limite", 1750, 11.0, 80,
     _curva([(4000, 3000, 4.6), (6000, 2950, 5.9), (8000, 2800, 7.2), (10000, 2550, 8.4), (12000, 2150, 9.3), (13500, 1750, 9.8)]), 31200),
    ("DEMO-LL-560", "Limit-load 560 (FICTÍCIO)", "centrifugo_limite", 1150, 15.0, 80,
     _curva([(8000, 2600, 8.1), (11000, 2550, 9.9), (14000, 2400, 11.6), (17000, 2150, 13.0), (20000, 1750, 14.0)]), 39900),
    ("DEMO-AX-800", "Axial de parede 800 (FICTÍCIO)", "axial", 1150, 1.1, 60,
     _curva([(4000, 160, 0.55), (8000, 130, 0.70), (12000, 85, 0.82), (15000, 40, 0.88), (17000, 0, 0.90)]), 4200),
    ("DEMO-AX-1000", "Axial de parede 1000 (FICTÍCIO)", "axial", 850, 1.5, 60,
     _curva([(6000, 180, 0.75), (12000, 150, 0.98), (18000, 100, 1.15), (22000, 50, 1.25), (25000, 0, 1.30)]), 5600),
]


def componentes_demo() -> list[dict]:
    out = []
    esp = {d: (0.5 if d <= 200 else 0.65 if d <= 450 else 0.8) for d in range(100, 850, 50)}
    for d in range(100, 850, 50):
        t = esp[d]
        massa = math.pi * d / 1000 * t / 1000 * 3.0 * 7850  # demonstrativo: casca cilíndrica de aço, sem costuras
        out.append(dict(codigo=f"DEMO-DT-{d}", categoria="duto_circular", descricao=f"Duto Ø{d} galvanizado #{t} mm (FICTÍCIO)", diametro_mm=d,
                        espessura_mm=t, material="galvanizado", comprimento_m=3.0, massa_kg=round(massa, 2), unidade="pç",
                        custo_unitario=round(40 + d * 0.55, 2)))
        for a in (90, 45, 30):
            out.append(dict(codigo=f"DEMO-CV{a}-{d}", categoria="curva", descricao=f"Curva {a}° Ø{d} R/D 1,5 (FICTÍCIO)", diametro_mm=d,
                            angulo_graus=a, material="galvanizado", espessura_mm=t, custo_unitario=round(25 + d * 0.35 * a / 90, 2)))
        out.append(dict(codigo=f"DEMO-SP-{d}", categoria="suporte", descricao=f"Suporte para duto Ø{d} (FICTÍCIO)", diametro_mm=d, custo_unitario=round(18 + d * 0.05, 2)))
        for d2 in range(100, d, 50):
            out.append(dict(codigo=f"DEMO-RD-{d}-{d2}", categoria="reducao", descricao=f"Redução Ø{d}→Ø{d2} (FICTÍCIO)", diametro_mm=d, diametro2_mm=d2,
                            custo_unitario=round(30 + d * 0.25, 2)))
            out.append(dict(codigo=f"DEMO-DV-{d}-{d2}", categoria="derivacao", descricao=f"Derivação Ø{d} × ramal Ø{d2} (FICTÍCIO)", diametro_mm=d, diametro2_mm=d2,
                            custo_unitario=round(60 + d * 0.4, 2)))
    out.append(dict(codigo="DEMO-FL", categoria="flange", descricao="Flange cantoneira (FICTÍCIO)", custo_unitario=22.0))
    out.append(dict(codigo="DEMO-CAP", categoria="captor", descricao="Captor padrão em chapa (FICTÍCIO)", custo_unitario=380.0))
    for c in out:
        c["demonstrativo"] = True
    return out


def rede_demo():
    return {
        "nodes": [
            {"id": "C1", "type": "captor", "x": 4, "y": 4, "label": "C1 Serra", "captor": {"tipo": "abertura_flangeada", "processo": "alta_dispersao", "distancia_m": 0.15, "area_face_m2": 0.04, "entrada": "flangeada"}},
            {"id": "C2", "type": "captor", "x": 4, "y": 11, "label": "C2 Plaina", "captor": {"tipo": "vazao_informada", "vazao_m3h": 1800, "entrada": "flangeada"}},
            {"id": "C3", "type": "captor", "x": 13, "y": 11, "label": "C3 Tupia", "captor": {"tipo": "vazao_informada", "vazao_m3h": 1400, "entrada": "flangeada"}},
            {"id": "C4", "type": "captor", "x": 13, "y": 4, "label": "C4 Lixadeira", "captor": {"tipo": "abertura_livre", "processo": "media_dispersao", "distancia_m": 0.2, "area_face_m2": 0.06, "entrada": "livre"}},
            {"id": "F1", "type": "filtro", "x": 24, "y": 7.5, "label": "Filtro de mangas", "filtro_tipo": "mangas"},
            {"id": "E1", "type": "exaustor", "x": 27, "y": 7.5, "label": "Exaustor"},
            {"id": "D1", "type": "descarga", "x": 27, "y": 13, "label": "Chaminé"},
        ],
        "segments": [
            {"id": "S1", "from": "F1", "to": "E1", "label": "S1"},
            {"id": "S2", "from": "E1", "to": "D1", "label": "S2"},
        ],
    }


def inicializar(db: Session):
    s = get_settings()
    # histórico de versões implantadas
    if not db.scalars(select(Versao).where(Versao.versao == s.app_version, Versao.git_sha == s.git_sha)).first():
        db.add(Versao(versao=s.app_version, git_sha=s.git_sha, ambiente=s.app_env))
    if not db.scalar(select(func.count(Usuario.id))):
        db.add(Usuario(email=s.admin_email.lower(), nome=s.admin_nome, perfil="administrador", senha_hash=hash_senha(s.admin_password)))
    if s.seed_demo:
        semear_demo(db)
    db.commit()


def semear_demo(db: Session):
    chaves = set(db.scalars(select(ParametroTecnico.chave)).all())
    for p in PARAMETROS_DEMO:
        if p["chave"] not in chaves:
            db.add(ParametroTecnico(chave=p["chave"], valor=p["valor"], unidade=p["unidade"], categoria=p.get("categoria", "Geral"),
                                    referencia=p["referencia"], status="proposto", demonstrativo=True))
    if not db.scalar(select(func.count(Exaustor.id))):
        for cod, mod, tipo, rpm, pm, tmax, curva, preco in EXAUSTORES_DEMO:
            db.add(Exaustor(codigo=cod, modelo=mod, tipo=tipo, rotacao_rpm=rpm, potencia_motor_kw=pm, temperatura_max_c=tmax, curva=curva,
                            tipo_pressao_curva="estatica", densidade_referencia=1.2, preco=preco, demonstrativo=True, status="proposto",
                            observacoes=AVISO))
    if not db.scalar(select(func.count(ComponenteDuto.id))):
        for c in componentes_demo():
            db.add(ComponenteDuto(**c))
    if not db.scalar(select(func.count(Projeto.id))):
        cli = Cliente(nome="Indústria Exemplo Ltda. (FICTÍCIO)", industria="Marcenaria demonstrativa", endereco="Endereço fictício",
                      contato_nome="Contato fictício", atividade="Fabricação de móveis", demonstrativo=True,
                      observacoes=AVISO)
        db.add(cli)
        db.flush()
        ent = {
            "temperatura_c": {"valor": 25, "unidade": "°C", "rotulo": "Temperatura do ar transportado", "status": "estimado", "fonte": AVISO},
            "altitude_m": {"valor": 760, "unidade": "m", "rotulo": "Altitude do local", "status": "estimado", "fonte": AVISO},
            "contaminante": {"valor": "poeira_madeira", "unidade": "", "rotulo": "Contaminante (poeira)", "status": "estimado", "fonte": AVISO},
            "material_dutos": {"valor": "galvanizado", "unidade": "", "rotulo": "Material dos dutos", "status": "estimado", "fonte": AVISO},
            "comprimento_m": {"valor": 30, "unidade": "m", "rotulo": "Comprimento do ambiente", "status": "estimado", "fonte": AVISO},
            "largura_m": {"valor": 15, "unidade": "m", "rotulo": "Largura do ambiente", "status": "estimado", "fonte": AVISO},
            "pe_direito_m": {"valor": 7, "unidade": "m", "rotulo": "Pé-direito", "status": "estimado", "fonte": AVISO},
            "horas_operacao_ano": {"valor": 2200, "unidade": "h", "rotulo": "Horas de operação por ano", "status": "estimado", "fonte": AVISO},
        }
        amb = {
            "contorno": [[0, 0], [30, 0], [30, 15], [0, 15]],
            "pilares": [{"pontos": [[x - 0.2, y - 0.2], [x + 0.2, y - 0.2], [x + 0.2, y + 0.2], [x - 0.2, y + 0.2]]} for x in (10, 20) for y in (0.2, 7.5, 14.8)],
            "obstaculos": [{"nome": "Bancada", "pontos": [[7, 6.5], [10.5, 6.5], [10.5, 8.5], [7, 8.5]]},
                           {"nome": "Estoque", "pontos": [[16, 2], [19, 2], [19, 6], [16, 6]]}],
        }
        p = Projeto(codigo="DEMO-0001", nome="Exaustão de pó de madeira — DEMONSTRATIVO", cliente_id=cli.id, modulo="poeira",
                    status="rascunho", descricao=AVISO, entradas=ent, ambiente=amb, riscos={"poeira_combustivel": True},
                    checklist_seguranca={}, demonstrativo=True)
        db.add(p)
        db.flush()
        db.add(Rede(projeto_id=p.id, dados=rede_demo()))
        p2 = Projeto(codigo="DEMO-0002", nome="Renovação de ar de galpão — DEMONSTRATIVO", cliente_id=cli.id, modulo="renovacao",
                     status="rascunho", descricao=AVISO, demonstrativo=True, riscos={}, checklist_seguranca={}, ambiente={"contorno": [[0, 0], [40, 0], [40, 20], [0, 20]]},
                     entradas={
                         "comprimento_m": {"valor": 40, "unidade": "m", "rotulo": "Comprimento do ambiente", "status": "estimado", "fonte": AVISO},
                         "largura_m": {"valor": 20, "unidade": "m", "rotulo": "Largura do ambiente", "status": "estimado", "fonte": AVISO},
                         "pe_direito_m": {"valor": 8, "unidade": "m", "rotulo": "Pé-direito", "status": "estimado", "fonte": AVISO},
                         "altitude_m": {"valor": 760, "unidade": "m", "rotulo": "Altitude do local", "status": "estimado", "fonte": AVISO},
                         "temperatura_c": {"valor": 30, "unidade": "°C", "rotulo": "Temperatura interna", "status": "estimado", "fonte": AVISO},
                         "uso": {"valor": "industrial_geral", "unidade": "", "rotulo": "Uso do ambiente", "status": "estimado", "fonte": AVISO},
                         "ocupantes": {"valor": 40, "unidade": "pessoas", "rotulo": "Número de ocupantes", "status": "estimado", "fonte": AVISO},
                         "modo_pressao": {"valor": "negativa", "unidade": "", "rotulo": "Pressurização desejada", "status": "estimado", "fonte": AVISO},
                     })
        db.add(p2)
        db.flush()
        db.add(Rede(projeto_id=p2.id, dados={"nodes": [], "segments": []}))
