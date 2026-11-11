"""Motor de cálculos de engenharia (independente de IA, banco de dados e web).

Todas as funções recebem dados explícitos e devolvem resultados acompanhados de
fórmulas, unidades e hipóteses (ver ``trace.py``). Nenhum parâmetro técnico é
inventado aqui: coeficientes dependentes de norma/material/contaminante chegam
pelo ``ParameterSet`` e são registrados com seu status de aprovação.
"""

ENGINE_VERSION = "0.1.0"
