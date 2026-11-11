"""Verificações de segurança obrigatórias por tipo de risco.

O software não substitui as análises de risco exigidas. Ele apenas impede a
aprovação técnica enquanto os itens aplicáveis não forem confirmados por um
engenheiro responsável. Referências citadas são indicativas: verificar as
edições vigentes e a legislação local.
"""

from __future__ import annotations

RISCOS = {
    "poeira_combustivel": {
        "titulo": "Poeira combustível",
        "referencias": "Ex.: NFPA 652 / NFPA 660, ABNT NBR IEC 60079-10-2 (verificar edições vigentes e exigências locais)",
        "itens": [
            "Análise de risco de poeira combustível realizada e anexada",
            "Classificação de áreas para poeiras realizada",
            "Proteção do coletor/filtro contra explosão definida (alívio, supressão ou contenção) e isolamento entre equipamentos",
            "Aterramento e equipotencialização de dutos, captores e filtros especificados",
            "Equipamentos elétricos e mecânicos compatíveis com a zona classificada",
            "Velocidade mínima de transporte verificada em todos os trechos (sem acúmulo de pó)",
            "Exaustor posicionado/construído de forma adequada ao risco (ex.: lado limpo, construção antifaiscante quando aplicável)",
        ],
    },
    "atmosfera_explosiva": {
        "titulo": "Atmosfera explosiva (gases/vapores inflamáveis)",
        "referencias": "Ex.: série ABNT NBR IEC 60079, NR-10 e NR-20 quando aplicáveis (verificar)",
        "itens": [
            "Classificação de áreas (gases/vapores) realizada",
            "Concentração na rede mantida abaixo da fração do LIE definida em projeto, com memória de cálculo",
            "Motor e componentes elétricos certificados para a zona",
            "Construção do ventilador adequada (antifaiscante) e aterramento especificado",
            "Intertravamentos e alarmes definidos",
        ],
    },
    "contaminante_perigoso": {
        "titulo": "Contaminante perigoso (tóxico, corrosivo, cancerígeno)",
        "referencias": "Ex.: NR-15, NR-9, FISPQ do produto e legislação ambiental aplicável (verificar)",
        "itens": [
            "FISPQ/FDS do contaminante anexada",
            "Compatibilidade química de materiais de dutos, vedações e exaustor verificada",
            "Necessidade de tratamento do efluente (lavador, carvão, filtro absoluto etc.) avaliada",
            "Ponto de descarga avaliado quanto a reentrada e vizinhança",
            "Requisitos de licenciamento ambiental verificados",
        ],
    },
    "temperatura_elevada": {
        "titulo": "Temperatura elevada",
        "referencias": "Dados do fabricante e projeto térmico",
        "itens": [
            "Limite de temperatura do exaustor e do filtro verificado",
            "Dilatação térmica e isolamento dos dutos considerados",
            "Correção de densidade aplicada na seleção do equipamento",
        ],
    },
}

FORA_DO_ESCOPO = {
    "controle_fumaca_incendio": (
        "Sistemas de controle de fumaça de incêndio exigem projeto específico conforme regulamentação do Corpo de "
        "Bombeiros local e normas aplicáveis. Este software NÃO emite aprovação para esse tipo de sistema."
    ),
}


def avaliar(riscos: dict[str, bool], checklist: dict[str, dict]) -> dict:
    """riscos: {chave: bool}; checklist: {"<risco>::<indice>": {"ok": bool, "por": str, "em": str}}."""
    pendencias, aplicaveis, bloqueios = [], [], []
    for chave, ativo in riscos.items():
        if not ativo:
            continue
        if chave in FORA_DO_ESCOPO:
            bloqueios.append(FORA_DO_ESCOPO[chave])
            continue
        r = RISCOS.get(chave)
        if not r:
            continue
        itens = []
        for i, txt in enumerate(r["itens"]):
            k = f"{chave}::{i}"
            st = checklist.get(k) or {}
            ok = bool(st.get("ok"))
            itens.append({"chave": k, "texto": txt, "ok": ok, "por": st.get("por"), "em": st.get("em")})
            if not ok:
                pendencias.append(f"{r['titulo']}: {txt}")
        aplicaveis.append({"risco": chave, "titulo": r["titulo"], "referencias": r["referencias"], "itens": itens})
    return {"aplicaveis": aplicaveis, "pendencias": pendencias, "bloqueios": bloqueios,
            "liberado": not pendencias and not bloqueios}
