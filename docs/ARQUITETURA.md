# Arquitetura

## Visão geral

```
Navegador (React + TypeScript, interface pt-BR)
        │  HTTPS (Caddy)
        ▼
FastAPI (Python 3.13) ── um contêiner por ambiente, serve a API (/api) e o frontend compilado
   ├── routers/        API REST (autenticação, projetos, visitas, plantas, catálogo, cálculos, exportações…)
   ├── services.py     orquestração banco ⇄ motor de cálculo, regras de aprovação
   ├── engine/         MOTOR DE CÁLCULO (puro Python, sem banco, sem web, sem IA)
   ├── cad/            importação DXF/PDF/DWG, detecção heurística, exportação DXF
   ├── docs/           memorial de cálculo, lista de materiais (CSV/XLSX/PDF), prancha PDF
   ├── assistant/      assistente técnico (Claude) com ferramentas somente leitura
   └── storage.py      arquivos enviados (volume persistente)
        │
        ▼
PostgreSQL 16 (um banco por ambiente) + backups diários (pg_dump)
```

### Decisões e justificativas

| Decisão | Motivo |
|---|---|
| **Vite + React + TypeScript** (em vez de Next.js) | A aplicação é interna, autenticada e não precisa de renderização no servidor nem SEO. Um SPA compilado é servido pelo próprio FastAPI: **um único contêiner por ambiente**, o que simplifica a publicação, a homologação e o retorno a versões anteriores. |
| **FastAPI + SQLAlchemy 2 + Alembic** | Tipagem, documentação automática da API (`/api/docs`), migrações versionadas e reversíveis. |
| **PostgreSQL** (SQLite apenas para testes/desenvolvimento rápido) | Banco centralizado, robusto e com backup simples via `pg_dump`. Os testes rodam nos dois. |
| **Motor de cálculo isolado** (`backend/app/engine`) | Cálculos reproduzíveis e auditáveis, testáveis sem banco/web. A IA não tem acesso de escrita a ele; só lê resultados. Cada execução registra versão do motor, hash SHA-256 das entradas, fórmulas, substituições, hipóteses e parâmetros usados com seu status. |
| **Parâmetros técnicos cadastráveis** | Coeficientes (K de conexões, rugosidade, velocidades de captura/transporte, perda de filtros, taxas de renovação…) ficam no banco com status *proposto/aprovado*, referência técnica e trilha de auditoria. O motor nunca usa valores embutidos. |
| **ezdxf** para DXF, **pdfplumber + pypdfium2** para PDF | Bibliotecas maduras com licenças permissivas (MIT/BSD/Apache). PyMuPDF foi evitado por ser AGPL. |
| **DWG via conversor externo** | Bibliotecas DXF não leem DWG. Há suporte opcional ao ODA File Converter (configurável), sem ele o usuário exporta DXF no AutoCAD. |
| **Shapely + A\*** para roteamento | Rasterização da planta com folgas em torno de obstáculos e busca A* ortogonal com penalidade de curvas; gera árvore captores → exaustor. |
| **Caddy + Docker Compose em um servidor (VPS)** | HTTPS automático (Let's Encrypt), dois ambientes isolados no mesmo servidor, custo e operação baixos. A mesma imagem roda em qualquer provedor de contêineres. |
| **GitHub Actions + GHCR** | Testes antes de publicar, imagens versionadas e imutáveis, implantação por SSH com backup e retorno automático. |

## Regras de engenharia implementadas

* **Continuidade**: vazão de cada trecho = soma das vazões a montante.
* **Captação**: Dalla Valle `Q = Vc·(10X² + A)` (com fator de flange), enclausuramento `Q = Vf·A`, coifa sobre fonte fria `Q = k·P·H·V`; fonte quente bloqueia (método de pluma não implementado).
* **Atrito**: Darcy-Weisbach com Colebrook-White (iterativo), viscosidade por Sutherland, densidade por gás ideal + atmosfera ISA (altitude).
* **Perdas localizadas**: `ΔP = ΣK·VP` — curvas (proporcionais ao ângulo a partir do K de 90°), entradas de ramal (interpolação 30°/45°/90°), transições, entrada de captor e saída; filtros/equipamentos por valor cadastrado ou informado.
* **Ventilador**: `FTP = ΔP_sucção(ramo governante) + ΔP_descarga`; `FSP = FTP − VP_saída`; curva do sistema `ΔP = k·Q²`.
* **Equilíbrio**: razão entre perdas de ramais que se encontram; acima do limite cadastrado → desequilíbrio (redimensionar/registrar); abaixo → vazão corrigida `Q·√(P_gov/P_ramal)`.
* **Seleção**: interseção exata curva × sistema por trecho linear, **sem extrapolação**, correção de densidade (leis dos ventiladores), limites de temperatura e de potência do motor, tolerância de superdimensionamento cadastrável; sem equipamento compatível → mensagem explícita.
* **Módulos distintos**: poeira (velocidade mínima de transporte obrigatória, filtro), fumos/gases (faixa de velocidade, temperatura, tratamento), renovação (trocas/hora × ocupação × carga térmica informada, balanço de pressão, áreas de entrada, quantidade de equipamentos).
* **Segurança**: poeira combustível, atmosfera explosiva, contaminante perigoso e temperatura elevada geram checklists que só o engenheiro confirma; **controle de fumaça de incêndio é sempre bloqueado**.

## Fluxo de aprovação

`rascunho → em_revisao → aprovado → liberado_fabricacao`

A aprovação (somente perfil engenheiro) é recusada enquanto houver: projeto demonstrativo, bloqueios do cálculo, parâmetros técnicos não aprovados, dados de entrada não confirmados, exaustor demonstrativo ou não aprovado, rede alterada após o cálculo, ou itens de segurança pendentes. Projeto aprovado fica imutável; reabri-lo gera nova revisão.

## Evolução planejada: 3D, Inventor e AutoCAD nativo

O modelo de rede já guarda nós e trechos com geometria; a evolução prevista:

1. **Coordenada Z e elevações** nos nós/trechos (o motor já aceita `comprimento_extra_m` e `curvas_extra` para trechos verticais).
2. **Exportação 3D neutra** (ex.: STEP/IFC, ou DXF 3D com sólidos) gerada no servidor.
3. **Conector Windows para Autodesk Inventor**: aplicativo local (add-in .NET usando a API COM do Inventor) que baixa um "pacote de projeto" (JSON com peças parametrizadas: dutos, curvas, reduções, derivações, flanges e o exaustor) e gera peças, montagens, desenhos de fabricação e planificação de chapas. Requer estação Windows com Inventor licenciado.
4. **Conector AutoCAD** (plug-in .NET/AutoLISP) para inserir/atualizar a rede diretamente no desenho aberto.
5. **Atualização dos conectores**: cada versão de conector será publicada como artefato assinado vinculado a uma versão da API; o conector consulta `/api/versao` e baixa atualizações compatíveis (mecanismo a implementar junto com o primeiro conector).

Nada disso está implementado na primeira versão — ver `PROGRESSO.md`.
