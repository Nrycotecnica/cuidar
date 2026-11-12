# Lki Industrial — Engenharia de Exaustão e Ventilação Industrial

Desenvolvido por **Diego Pereira**.

Aplicação web para automatizar projetos de **exaustão de poeiras**, **exaustão de fumaças/gases/vapores** e **renovação de ar**, da visita técnica à lista de materiais, com motor de cálculo auditável, catálogo próprio de exaustores e componentes, importação de plantas (DXF/PDF), exportação de desenho editável (DXF) e publicação online com ambientes de homologação e produção.

> **Importante.** Os resultados são preliminares até a aprovação de um profissional legalmente habilitado. A inteligência artificial não calcula, não inventa parâmetros e não aprova projetos. Os dados que acompanham a instalação (parâmetros técnicos, exaustores, componentes e projetos "DEMO") são **fictícios** e marcados como demonstrativos.

> Observação: este repositório também contém as páginas estáticas do app "Cuidar" (`index.html`, `privacidade.html`, `icone.png`), que não fazem parte deste sistema e não foram alteradas.

## Estrutura

```
backend/            API FastAPI + motor de cálculo + CAD + documentos (Python 3.13)
  app/engine/       motor de cálculo independente (testado isoladamente)
  alembic/          migrações do banco de dados
  tests/            testes automatizados (motor e API)
frontend/           interface React + TypeScript (Vite)
deploy/             servidor: homologação + produção, HTTPS, backups, scripts de atualização
docs/ARQUITETURA.md decisões técnicas, regras de engenharia e evolução (3D/Inventor)
.github/workflows/  CI (testes) e publicação automática
PROGRESSO.md        o que funciona, o que falta, limitações conhecidas
```

## Executar localmente

### Opção 1 — Docker (mais simples)

```bash
docker compose up --build
```
Acesse <http://localhost:8080>. Usuário inicial: `admin@exemplo.com` / `admin123` (somente em desenvolvimento; fora dele a aplicação exige senha e chave próprias).

### Opção 2 — sem Docker (desenvolvimento)

Pré-requisitos: Python 3.13, Node.js 22.

```bash
# Backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.manage migrar               # cria/atualiza o banco (SQLite em backend/dados/ por padrão)
uvicorn app.main:app --reload --port 8000

# Frontend (outro terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5173 (proxy /api → :8000)
```

Para usar PostgreSQL defina `DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/banco`.

### Variáveis de ambiente principais

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_ENV` | `desenvolvimento` | `desenvolvimento`, `homologacao` ou `producao` (aparece na faixa do topo) |
| `DATABASE_URL` | SQLite local | conexão do banco |
| `SECRET_KEY` | (fraca) | assinatura dos tokens — obrigatório ≥ 32 caracteres fora de desenvolvimento |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@exemplo.com` / `admin123` | administrador criado se não houver usuários |
| `SEED_DEMO` | `true` | carrega parâmetros, catálogo e projetos demonstrativos (fictícios) |
| `STORAGE_DIR` | `backend/dados/arquivos` | arquivos enviados |
| `ANTHROPIC_API_KEY` | vazio | habilita o assistente com IA (Claude); sem ela, modo de regras |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | modelo do assistente |
| `ODA_CONVERTER_PATH` | vazio | executável do ODA File Converter para importar DWG |

## Testes

```bash
cd backend && python -m pytest -q          # motor de cálculo + API (SQLite; use DATABASE_URL para PostgreSQL)
cd frontend && npm test && npm run build
```

## Como usar (roteiro rápido)

1. **Entrar** com o administrador e criar os usuários em *Administração* (perfis: administrador, engenheiro responsável, projetista, técnico de campo, orçamentista, operador de testes).
2. **Catálogo**: cadastrar ou importar (CSV/XLSX — há modelos para baixar) exaustores com curvas, componentes de dutos com custos, e revisar os **parâmetros técnicos**: substituir os valores demonstrativos por valores com referência e aprová-los (engenheiro).
3. **Visita técnica**: registrar cliente, ambiente, pontos de emissão, máquinas, riscos, fotos e documentos. O sistema lista os dados ainda a levantar. Criar o projeto a partir da visita.
4. **Projeto → Plantas**: importar DXF/PDF/imagem, confirmar ou calibrar a escala, revisar pilares/máquinas detectados e aplicar ao ambiente.
5. **Projeto → Rede**: posicionar captores, filtro, exaustor e descarga; **rotear automaticamente** (desvia de obstáculos e áreas bloqueadas) ou desenhar/editar manualmente; **calcular**.
6. **Projeto → Cálculo**: vazões, perdas, equilíbrio, ponto de operação, exaustor selecionado e rejeitados com motivo; gerar alternativas.
7. **Projeto → Documentos**: DXF editável (mm, camadas `VENT-*`, blocos com atributos, cotas), prancha PDF, memorial de cálculo, lista de materiais (CSV/XLSX/PDF).
8. **Segurança / Aprovação**: declarar riscos, cumprir checklists, enviar para revisão; o engenheiro aprova (bloqueado enquanto houver pendências) e libera para fabricação.
9. **Biblioteca de Projetos Anteriores**: anexar projetos antigos e comparar com projetos gerados.

## Instalação no Windows — um arquivo só (forma recomendada)

Ver [`deploy/windows/LEIAME.md`](deploy/windows/LEIAME.md): baixe [`LKI-INDUSTRIAL-Instalador.exe`](https://github.com/Nrycotecnica/cuidar/releases/download/lki-windows/LKI-INDUSTRIAL-Instalador.exe) e dê dois cliques — já traz o programa inteiro e libera o acesso pela rede local no firewall (só rede local). Sem Docker, sem administrador. Atualização pelo atalho **ATUALIZAR LKI INDUSTRIAL**. Alternativa pelo terminal: `INSTALAR-LKI-INDUSTRIAL.cmd`.

## Instalação local com Docker (alternativa)

Ver [`deploy/local/LEIAME.md`](deploy/local/LEIAME.md): roda no próprio computador com Docker Desktop (PostgreSQL), atalho ATUALIZAR e backup diário.

## Publicação online

Ver [`deploy/LEIAME-SERVIDOR.md`](deploy/LEIAME-SERVIDOR.md): push na `main` publica em **homologação**; tag `vX.Y.Z` publica em **produção** após aprovação; qualquer versão anterior pode ser reimplantada pelo GitHub Actions. Backup automático antes de cada atualização e diariamente.
