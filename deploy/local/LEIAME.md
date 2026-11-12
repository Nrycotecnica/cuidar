# Lki Industrial — instalação local (no seu computador)

Roda o sistema completo no próprio computador, sem custo de hospedagem, com **atualização automática** a partir do GitHub e **backup diário**. Os outros computadores da mesma rede (fábrica/escritório) acessam pelo navegador.

## Requisitos
- Windows 10/11 com o **Docker Desktop** instalado e aberto — https://www.docker.com/products/docker-desktop/ (instale com as opções padrão; ele pode pedir para reiniciar e para ativar o WSL 2).
- Internet para baixar as versões novas.

## Instalação (uma vez)
1. Baixe o projeto: no GitHub, **Code → Download ZIP**, e extraia (ex.: `C:\LkiIndustrial`). Ou `git clone https://github.com/Nrycotecnica/cuidar.git`.
2. Abra a pasta `deploy\local`.
3. Clique com o botão direito em **`instalar.ps1` → Executar com o PowerShell**.
   - Se o Windows bloquear, abra o PowerShell nessa pasta e rode:
     `powershell -ExecutionPolicy Bypass -File .\instalar.ps1`
4. Informe o **e-mail e a senha do administrador**. O script:
   - cria a configuração com senhas aleatórias para o banco e para os tokens (arquivo `.env` — não compartilhe);
   - baixa e inicia o sistema;
   - agenda a **atualização automática a cada 30 minutos** (Agendador de Tarefas: *LkiIndustrial-Atualizar*);
   - pergunta se deve liberar a porta 8080 no firewall para a rede local;
   - abre o navegador em **http://localhost:8080**.

Nos outros computadores da rede: `http://<IP-deste-computador>:8080` (o script mostra o IP ao final).

## Como funciona a atualização
1. Você (ou o Claude Code) envia mudanças para a branch `main` no GitHub.
2. O GitHub roda os testes e publica a imagem nova (`ghcr.io/nrycotecnica/cuidar:main`).
3. Em até 30 minutos, `atualizar.ps1` percebe a versão nova, **faz backup do banco** (`backups\pre-atualizacao-*.dump`) e reinicia o sistema. O registro fica em `atualizacoes.log`.

A versão instalada aparece na faixa do topo da tela e em **Administração**.

## Backups
- Diários, em `deploy\local\backups\` (banco `db-*.dump` e arquivos `arquivos-*.tar.gz`), mantidos por 14 dias.
- **Copie essa pasta para outro lugar** (OneDrive, Google Drive, HD externo) — se o computador estragar, os backups vão junto.

## Cuidados
- O sistema só funciona enquanto **o computador estiver ligado e o Docker Desktop aberto** (em *Settings → General*, marque "Start Docker Desktop when you sign in").
- O acesso é só pela rede local. Para acessar de fora (visitas a clientes), será preciso um túnel/VPN ou hospedagem online.
- Para parar: `desinstalar.ps1` (mantém os dados).

## Restaurar um backup do banco
No PowerShell, na pasta `deploy\local`:
```powershell
docker compose stop app
docker compose cp .\backups\NOME-DO-ARQUIVO.dump db:/tmp/r.dump
docker compose exec -T db pg_restore -U lki -d lki --clean --if-exists --no-owner /tmp/r.dump
docker compose start app
```
