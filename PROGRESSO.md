# PROGRESSO

Última atualização: 11/11/2026 — versão 0.1.0 (primeira versão funcional / MVP).

Legenda: ✅ funciona e foi verificado · 🟡 parcial · ⏳ não iniciado · 🔒 depende de algo externo

## Critérios de aceitação do MVP

| Critério | Situação | Como foi verificado |
|---|---|---|
| Cadastrar projeto e salvá-lo | ✅ | `tests/test_api.py::test_cadastro_projeto_persiste` |
| Dados persistem após fechar e abrir | ✅ | PostgreSQL com volume persistente; testes rodam em PostgreSQL e SQLite; reinício do servidor preserva dados |
| Importar e visualizar DXF válido | ✅ | `test_importar_e_visualizar_dxf` (entidades, camadas, blocos expandidos, detecção de pilar) + visualizador no frontend |
| Criar/editar rede simples | ✅ | `test_fluxo_rede_calculo_exportacao` (roteamento automático, edição e salvamento) + editor visual |
| Motor de cálculo reproduzível com casos conhecidos | ✅ | `tests/test_engine.py` — 26 casos: conversões exatas, densidade/viscosidade do ar, Colebrook (tubo liso Re=10⁵), Dalla Valle, ponto de operação com solução analítica, rede completa comparada com cálculo independente, mesmo hash/resultado em execuções repetidas |
| Cadastrar e consultar curva de exaustor | ✅ | `test_curva_exaustor_cadastrar_consultar`, `test_importar_exaustores_csv` (conversão mmca→Pa) |
| Exportar DXF editável aberto em software CAD compatível | ✅ | Auditoria do ezdxf sem erros, leitura por parser independente (`dxf-parser`, JavaScript) e **renderização no LibreCAD 2.x** (`librecad dxf2pdf`). ⚠️ Não foi testado no AutoCAD (não disponível neste ambiente) — abra um arquivo exportado no AutoCAD da empresa para confirmar |
| Exportar lista de componentes | ✅ | CSV, XLSX e PDF (`test_fluxo_rede_calculo_exportacao`) |
| Anexar projeto antigo | ✅ | `test_upload_arquivo_e_projeto_antigo` (anexo + download + comparação) |
| Testes automatizados das funcionalidades essenciais | ✅ | 47 testes backend (motor + API + assistente simulado); testes do frontend (ver abaixo) |
| Publicar atualização em homologação sem interferir na produção | 🟡 | Mecanismo implementado (`deploy/`, `.github/workflows/deploy.yml`) e simulado localmente com Docker (ver seção Infraestrutura). 🔒 Falta um servidor e domínios reais para colocar no ar |

## O que já funciona

### Backend / motor de cálculo
- ✅ Login JWT, 6 perfis com matriz de permissões, troca de senha, gestão de usuários.
- ✅ Auditoria de todas as alterações (projetos, entradas, parâmetros, catálogo, aprovações, exportações).
- ✅ Clientes, projetos (3 módulos), entradas com status *confirmado / estimado / não confirmado* (só o engenheiro confirma; alteração de valor confirmado volta a "não confirmado").
- ✅ Visita técnica digital com lista automática de dados a levantar e criação do projeto inicial com dados parciais.
- ✅ Motor de cálculo: ar (ISA + gás ideal + Sutherland), Darcy-Weisbach/Colebrook, perdas singulares parametrizadas, captores (Dalla Valle, flange, enclausuramento, coifa fria), ramo governante, equilíbrio de junções, FTP/FSP, curva do sistema, ponto de operação exato sem extrapolação, correção de densidade, seleção com motivos de rejeição, três estratégias de dimensionamento e comparação de alternativas (pressão, potência, energia anual, massa, custo), renovação de ar (trocas/h, ocupação, carga térmica informada, balanço de pressão, quantidade de equipamentos, área de entrada, sugestão de posicionamento).
- ✅ Roteamento automático ortogonal (A*) evitando pilares, máquinas e regiões bloqueadas, preservando trechos travados e o lado de descarga.
- ✅ Verificações de segurança com checklist (poeira combustível, atmosfera explosiva, contaminante perigoso, temperatura) e bloqueio permanente para controle de fumaça de incêndio.
- ✅ Fluxo de aprovação com bloqueios (demonstrativo, parâmetros não aprovados, entradas não confirmadas, exaustor não aprovado, rede alterada, segurança).
- ✅ Catálogo: exaustores (curvas, limites, preço), componentes de dutos (diâmetros, espessuras, materiais, comprimentos, curvas, reduções, derivações, flanges, suportes, custos), parâmetros técnicos com aprovação; importação CSV/XLSX com modelos para download.
- ✅ Importação DXF (unidades $INSUNITS, blocos, polilinhas com arcos, splines, textos), PDF vetorial (com imagem de fundo) e imagens; calibração por dois pontos; detecção heurística de contorno, pilares, máquinas e pé-direito (editável).
- ✅ Exportações: DXF (mm, camadas VENT-/ARQ-/REF-, blocos com atributos, cotas, legenda e tabela de trechos, planta de referência), prancha PDF A3 em escala normalizada, memorial de cálculo PDF (entradas, hipóteses, parâmetros com status, memória passo a passo, trechos, equilíbrio, gráfico curva × sistema, seleção, segurança, aprovação), lista de materiais CSV/XLSX/PDF com situação PRELIMINAR/LIBERADO.
- ✅ Biblioteca de projetos anteriores com anexos e comparação (vazão, pressões, potência, comprimento, captores, exaustor, diâmetros) com tolerância.
- ✅ Assistente técnico: Claude com ferramentas somente leitura (projeto, pendências, cálculo, catálogo, comparação de exaustores pelo motor, alternativas); modo de regras sem IA quando não há chave.
- ✅ Painel administrativo: versão instalada, commit, migração do banco, histórico de versões, auditoria.

### Frontend
- (preenchido abaixo após verificação)

### Infraestrutura
- ✅ Dockerfile único (frontend compilado + API), `docker compose up` para desenvolvimento.
- ✅ Servidor com homologação e produção isolados, HTTPS automático (Caddy), backups diários, backup antes de cada atualização, retorno automático se a nova versão não ficar saudável, script de restauração.
- ✅ GitHub Actions: CI (PostgreSQL + SQLite, `alembic check`, frontend) e publicação (main → homologação; tag → produção com aprovação; reimplantação manual de versões anteriores).

## Em andamento / próximos passos sugeridos
1. 🔒 Contratar/definir servidor e domínios e configurar os segredos do GitHub (ver `deploy/LEIAME-SERVIDOR.md`).
2. 🔒 Substituir os dados demonstrativos por dados reais: curvas dos exaustores fabricados, catálogo de dutos e custos, e parâmetros técnicos com referência — e aprová-los.
3. Validar o motor contra projetos antigos reais da empresa (Biblioteca) e registrar os casos como testes de referência.
4. Abrir os DXF exportados no AutoCAD da empresa e ajustar padrões de camadas/cores/textos ao padrão interno.

## Ainda não implementado
- ⏳ Integração direta com AutoCAD (plug-in) e com Autodesk Inventor (conector Windows) — arquitetura descrita em `docs/ARQUITETURA.md`.
- ⏳ Modelagem 3D, desenhos de fabricação, planificação de chapas.
- ⏳ Método de pluma térmica para coifas sobre fontes quentes (hoje bloqueia e exige vazão informada justificada).
- ⏳ Dimensionamento automático de dutos retangulares (aceitos com dimensões informadas).
- ⏳ Leis dos ventiladores para variação de rotação (seleção usa somente a curva cadastrada).
- ⏳ Reconhecimento automático em imagens raster/PDF digitalizado (apenas calibração e desenho manual).
- ⏳ Comparação geométrica automática de trajetos com projetos antigos.
- ⏳ Armazenamento de arquivos em serviço de objetos (S3/MinIO) — hoje volume local com backup diário.
- ⏳ Fila de trabalhos para tarefas longas (importações grandes rodam na requisição).
- ⏳ Cópia automática dos backups para fora do servidor.
- ⏳ Recuperação de senha por e-mail.

## Limitações conhecidas
- Todos os parâmetros técnicos, exaustores e componentes carregados na instalação são **fictícios**. Os resultados dos projetos DEMO não servem para instalação.
- A detecção de paredes/pilares/máquinas é heurística (nomes de camadas e dimensões) e precisa de revisão manual.
- DWG só é importado se o ODA File Converter estiver instalado e configurado no servidor (não testado neste ambiente); caso contrário, exportar DXF no AutoCAD.
- O assistente com IA foi testado com cliente simulado; a chamada real depende de `ANTHROPIC_API_KEY` (não disponível no ambiente de desenvolvimento).
- Token de sessão guardado no navegador (localStorage); recomenda-se uso apenas em rede/computadores confiáveis até a adoção de cookies httpOnly.
- Perdas de transições e curvas usam coeficientes simplificados (K proporcional ao ângulo); casos especiais devem usar singularidades informadas no trecho.
