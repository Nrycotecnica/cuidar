"""Parâmetros técnicos DEMONSTRATIVOS (fictícios para testes).

ATENÇÃO: valores apenas para permitir o funcionamento do protótipo. Todos são
cadastrados com status "proposto" e marcados como demonstrativos. Antes de
qualquer uso real devem ser conferidos com literatura técnica e normas
vigentes (ex.: manual da ACGIH "Industrial Ventilation", ABNT NBR 16401,
dados de fabricantes) e aprovados por responsável técnico.
"""

REF = "VALOR DEMONSTRATIVO — conferir em literatura/norma e aprovar antes do uso"

PARAMETROS_DEMO = [
    # Rugosidade absoluta (mm)
    {"chave": "rugosidade.galvanizado", "valor": 0.15, "unidade": "mm", "categoria": "Rugosidade"},
    {"chave": "rugosidade.aco_carbono", "valor": 0.045, "unidade": "mm", "categoria": "Rugosidade"},
    {"chave": "rugosidade.inox", "valor": 0.015, "unidade": "mm", "categoria": "Rugosidade"},
    {"chave": "rugosidade.pvc", "valor": 0.0015, "unidade": "mm", "categoria": "Rugosidade"},
    # Velocidade mínima de transporte (m/s)
    {"chave": "vel_transporte_min.poeira_madeira", "valor": 18.0, "unidade": "m/s", "categoria": "Velocidade de transporte"},
    {"chave": "vel_transporte_min.poeira_metalica", "valor": 20.0, "unidade": "m/s", "categoria": "Velocidade de transporte"},
    {"chave": "vel_transporte_min.poeira_leve", "valor": 15.0, "unidade": "m/s", "categoria": "Velocidade de transporte"},
    {"chave": "vel_duto_max.poeira", "valor": 25.0, "unidade": "m/s", "categoria": "Velocidade de transporte"},
    {"chave": "vel_duto_min.fumos", "valor": 10.0, "unidade": "m/s", "categoria": "Velocidade em dutos"},
    {"chave": "vel_duto_max.fumos", "valor": 15.0, "unidade": "m/s", "categoria": "Velocidade em dutos"},
    {"chave": "vel_duto_min.renovacao", "valor": 5.0, "unidade": "m/s", "categoria": "Velocidade em dutos"},
    {"chave": "vel_duto_max.renovacao", "valor": 10.0, "unidade": "m/s", "categoria": "Velocidade em dutos"},
    # Velocidade de captura (m/s)
    {"chave": "vel_captura.baixa_dispersao", "valor": 0.5, "unidade": "m/s", "categoria": "Velocidade de captura"},
    {"chave": "vel_captura.media_dispersao", "valor": 1.0, "unidade": "m/s", "categoria": "Velocidade de captura"},
    {"chave": "vel_captura.alta_dispersao", "valor": 2.5, "unidade": "m/s", "categoria": "Velocidade de captura"},
    {"chave": "vel_captura.solda", "valor": 0.5, "unidade": "m/s", "categoria": "Velocidade de captura"},
    {"chave": "fator_flange", "valor": 0.75, "unidade": "-", "categoria": "Captores"},
    {"chave": "fator_coifa", "valor": 1.4, "unidade": "-", "categoria": "Captores"},
    # Coeficientes de perda (K, adimensional)
    {"chave": "k_entrada_captor.livre", "valor": 0.93, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_entrada_captor.flangeada", "valor": 0.49, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_entrada_captor.boca_sino", "valor": 0.04, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_entrada_captor.coifa", "valor": 0.25, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_curva_90", "valor": 0.39, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_entrada_ramal_30", "valor": 0.18, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_entrada_ramal_45", "valor": 0.28, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_entrada_ramal_90", "valor": 1.0, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_transicao", "valor": 0.1, "unidade": "-", "categoria": "Perdas singulares"},
    {"chave": "k_saida", "valor": 1.0, "unidade": "-", "categoria": "Perdas singulares"},
    # Equipamentos
    {"chave": "dp_filtro.mangas", "valor": 1200.0, "unidade": "Pa", "categoria": "Equipamentos"},
    {"chave": "dp_filtro.cartucho", "valor": 1000.0, "unidade": "Pa", "categoria": "Equipamentos"},
    {"chave": "dp_filtro.lavador", "valor": 800.0, "unidade": "Pa", "categoria": "Equipamentos"},
    {"chave": "dp_filtro.generico", "valor": 500.0, "unidade": "Pa", "categoria": "Equipamentos"},
    # Critérios de projeto
    {"chave": "desequilibrio_max", "valor": 1.2, "unidade": "-", "categoria": "Critérios"},
    {"chave": "tolerancia_vazao_selecao", "valor": 0.20, "unidade": "-", "categoria": "Critérios"},
    {"chave": "espacamento_suportes_m", "valor": 3.0, "unidade": "m", "categoria": "Fabricação"},
    # Renovação de ar
    {"chave": "renov_trocas_h.industrial_geral", "valor": 10.0, "unidade": "trocas/h", "categoria": "Renovação"},
    {"chave": "renov_trocas_h.deposito", "valor": 4.0, "unidade": "trocas/h", "categoria": "Renovação"},
    {"chave": "renov_trocas_h.fundicao", "valor": 30.0, "unidade": "trocas/h", "categoria": "Renovação"},
    {"chave": "vazao_pessoa.industrial_geral", "valor": 27.0, "unidade": "m³/h·pessoa", "categoria": "Renovação"},
    {"chave": "desbalanco_pressao_pct", "valor": 10.0, "unidade": "%", "categoria": "Renovação"},
    {"chave": "dp_sistema_renovacao", "valor": 50.0, "unidade": "Pa", "categoria": "Renovação"},
    {"chave": "vel_face_veneziana", "valor": 2.0, "unidade": "m/s", "categoria": "Renovação"},
]

for _p in PARAMETROS_DEMO:
    _p.setdefault("referencia", REF)
    _p.setdefault("status", "proposto")
    _p.setdefault("demonstrativo", True)
