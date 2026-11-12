"""Motor de cálculos de engenharia (independente de IA, banco de dados e web).

Todas as funções recebem dados explícitos e devolvem resultados acompanhados de
fórmulas, unidades e hipóteses (ver ``trace.py``). Nenhum parâmetro técnico é
inventado aqui: coeficientes dependentes de norma/material/contaminante chegam
pelo ``ParameterSet`` e são registrados com seu status de aprovação.
"""

# 0.2.0: descidas/subidas verticais a partir das cotas (cotas.py). Cálculos
# antigos guardam a versão com que foram feitos — é ela que diz se a descida
# até o captor estava ou não no comprimento.
ENGINE_VERSION = "0.2.0"
