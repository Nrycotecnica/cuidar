# Publicação online (homologação e produção)

Há duas formas suportadas. **A escolhida para começar é o Render** (plataforma gerenciada); a opção de servidor próprio (VPS) continua documentada mais abaixo.

## Opção 1 — Render (plataforma gerenciada) — recomendada

O arquivo [`render.yaml`](../render.yaml) (Blueprint) cria o projeto **lki-industrial** com dois ambientes isolados:

| Ambiente | Serviço web | Banco PostgreSQL | Atualiza quando |
|---|---|---|---|
| homologacao | `lki-homologacao` (0.5 CPU / 512 MB, disco 5 GB) | `lki-db-homologacao` | há commit na `main` **e** os testes do GitHub passaram |
| producao | `lki-producao` (0.5 CPU / 512 MB, disco 10 GB) | `lki-db-producao` | a branch `producao` avança — só ao criar uma tag `vX.Y.Z` (workflow *Publicar*, com aprovação do ambiente `producao` no GitHub) |

Planos e região (`virginia`) foram escolhidos como ponto de partida e conferidos na documentação do Render em 11/2026; o consumo medido do sistema foi ≈140 MB de RAM. **Os planos são pagos** — confira os preços atuais no site do Render antes de aplicar. Instâncias gratuitas não servem: não têm disco persistente, "dormem" após 15 min sem uso e o banco gratuito expira em 30 dias.

### Passo a passo (uma vez)

1. Crie a branch `producao` publicando a primeira versão: no GitHub, crie a tag `v0.1.0` na `main` (ou rode `git tag v0.1.0 && git push origin v0.1.0`). O workflow *Publicar* roda os testes e cria a branch.
2. No Render: **New → Blueprint**, conecte o GitHub (autorize o repositório `cuidar`) e selecione o repositório. O Render lê o `render.yaml`.
3. Preencha os valores pedidos (`sync: false`) para cada ambiente: `ADMIN_EMAIL`, `ADMIN_PASSWORD` (senha forte, diferente em cada ambiente) e, se quiser IA no assistente, `ANTHROPIC_API_KEY`. `SECRET_KEY` é gerada automaticamente.
4. Clique em **Apply**. Ao final, cada serviço terá um endereço `https://lki-....onrender.com`.
5. **Domínio próprio**: em cada serviço → *Settings → Custom Domains*, adicione o subdomínio (ex.: `homologacao.seudominio.com.br` e `app.seudominio.com.br`) e crie no seu provedor de DNS o registro **CNAME** indicado pelo Render. O HTTPS é emitido automaticamente.

### Atualizações e retorno de versão

* `main` → homologação (automático, após os testes).
* Tag `vX.Y.Z` → produção (após aprovação).
* Voltar a produção para uma versão anterior: GitHub → Actions → *Publicar* → *Run workflow* → ambiente `producao` e a tag desejada (ex.: `v0.1.0`). No Render também é possível usar *Rollback* no histórico de deploys do serviço.
* Migrações do banco rodam automaticamente na inicialização de cada versão. Antes de publicar em produção uma versão que altera o banco, confira os backups do Render Postgres (disponibilidade e retenção dependem do plano — veja a documentação do Render).

## Opção 2 — Servidor próprio (VPS)

Arquitetura: **um servidor Linux com Docker** (VPS de qualquer provedor) roda dois ambientes isolados — cada um com seu contêiner da aplicação, seu banco PostgreSQL, seus arquivos e seus backups — atrás do Caddy, que emite certificados HTTPS automaticamente.

```
https://homologacao.seudominio.com.br ─┐                ┌─ app-homolog  ─ db-homolog  (+ backup diário)
                                       ├─ Caddy (443) ──┤
https://engenharia.seudominio.com.br ──┘                └─ app-producao ─ db-producao (+ backup diário)
```

## O que é necessário (e ainda não foi fornecido)

| Item | Para quê |
|---|---|
| Servidor Linux (2 vCPU / 4 GB RAM / 40 GB disco é um ponto de partida razoável — **avalie conforme o uso**) com Docker e Docker Compose | Rodar os ambientes |
| Dois nomes de domínio (ou subdomínios) apontando (registro DNS A/AAAA) para o IP do servidor, portas 80 e 443 abertas | HTTPS automático |
| Usuário SSH no servidor com permissão para usar Docker, e o par de chaves para o GitHub | Implantação automática |
| (Opcional) chave da API da Anthropic | Assistente com IA; sem ela o assistente funciona em modo de regras |
| (Opcional) ODA File Converter instalado na imagem/servidor | Importar DWG diretamente |

## Preparação do servidor (uma vez)

```bash
sudo mkdir -p /opt/ventilacao && sudo chown "$USER" /opt/ventilacao
git clone https://github.com/nrycotecnica/cuidar.git /opt/ventilacao   # ou copie apenas a pasta deploy/
cd /opt/ventilacao/deploy
cp .env.exemplo .env                      # ajuste domínios e tags
cp ambiente.env.exemplo homolog.env       # senhas e SECRET_KEY próprias da homologação
cp ambiente.env.exemplo producao.env      # senhas e SECRET_KEY próprias da produção; DATABASE_URL com @db-producao; SEED_DEMO=false
chmod 600 *.env
# se o repositório/pacote for privado:
echo "<token com read:packages>" | docker login ghcr.io -u <usuario-github> --password-stdin
docker compose -f docker-compose.servidor.yml --env-file .env up -d
```

## Configuração no GitHub (uma vez)

1. **Settings → Environments**: crie `homologacao` e `producao`. Em `producao`, ative **Required reviewers** (a publicação em produção passa a exigir aprovação manual).
2. **Settings → Secrets and variables → Actions**: `SSH_HOST`, `SSH_USER`, `SSH_KEY` (chave privada), `SSH_KNOWN_HOSTS` (saída de `ssh-keyscan <host>`). Variável opcional `PASTA_DEPLOY` (padrão `/opt/ventilacao/deploy`).
3. Enquanto os segredos não existirem, o workflow publica a imagem no GHCR e apenas avisa que a implantação foi ignorada.

## Ciclo de atualização

| Ação | Resultado |
|---|---|
| Merge/push na branch `main` | Testes → imagem `sha-xxxxxxx` → **homologação** atualizada automaticamente |
| Criar tag `vX.Y.Z` (ex.: `git tag v0.2.0 && git push origin v0.2.0`) | Testes → imagem `vX.Y.Z` → aguarda aprovação → **produção** |
| Actions → *Publicar* → *Run workflow* (ambiente + tag) | Reimplanta qualquer versão já publicada (retorno a versão anterior) |

O script `scripts/atualizar.sh` (executado no servidor pelo workflow):
1. faz `pg_dump` do banco do ambiente (`backups/<ambiente>/pre-atualizacao-*.dump`);
2. atualiza **somente** o contêiner do ambiente indicado (o outro ambiente não é tocado);
3. a aplicação aplica migrações do banco ao iniciar (Alembic);
4. aguarda a verificação de saúde; se falhar, volta automaticamente para a tag anterior e indica o backup para restauração.

Cada inicialização registra a versão no banco; o painel **Administração** mostra a versão instalada e o histórico. O arquivo `historico-implantacoes.log` no servidor registra todas as implantações.

## Backups e restauração

* Contêineres `backup-homolog` e `backup-producao` geram diariamente `db-*.dump` e `arquivos-*.tar.gz` em `deploy/backups/<ambiente>/` (retenção 14 e 30 dias). **Copie essa pasta para fora do servidor** (ex.: armazenamento de objetos) — isso ainda não está automatizado.
* Restaurar banco: `./scripts/restaurar.sh producao backups/producao/db-AAAAMMDD-HHMMSS.dump`.
* Restaurar arquivos: extrair o `arquivos-*.tar.gz` correspondente no volume do ambiente.

## Teste local da infraestrutura

É possível simular o servidor localmente com `CADDY_TLS="tls internal"`, domínios `homolog.localhost`/`producao.localhost` e `SEM_PULL=1 ./scripts/atualizar.sh ...` usando imagens construídas localmente (foi assim que a separação entre ambientes foi verificada — ver `PROGRESSO.md`).
