# LKI INDUSTRIAL para Windows — instalador de um arquivo só

Forma recomendada de instalar no computador de quem vai usar: **não precisa de Docker, nem de administrador, nem reiniciar.**

## Para quem vai instalar
1. Baixe **`LKI-INDUSTRIAL-Instalador.exe`** (≈ 70 MB, já traz o programa inteiro — instala até sem internet):
   https://github.com/Nrycotecnica/cuidar/releases/download/lki-windows/LKI-INDUSTRIAL-Instalador.exe
2. Dê **dois cliques**.
   - Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações → Executar assim mesmo** (o arquivo não tem assinatura digital paga).
3. Crie o **e-mail e a senha** do administrador, deixe marcado **"Permitir acesso pelos outros computadores da rede local"** e clique em **Instalar**.
   - No fim, o Windows pede **uma vez** permissão para o firewall: clique em **Sim**. A liberação vale só para a rede local (perfis Privado/Domínio, sub-rede local), nunca para a internet. Quem clicar "Não" instala do mesmo jeito e libera depois pelo Menu Iniciar → **LIBERAR REDE LKI INDUSTRIAL**.
4. Clique em **Abrir o sistema**. O LKI INDUSTRIAL aparece em **Configurações → Aplicativos instalados** (com Desinstalar). Na Área de Trabalho ficam três atalhos:
   - **LKI INDUSTRIAL** — abre o sistema (e avisa se há versão nova);
   - **ATUALIZAR LKI INDUSTRIAL** — instala a versão nova (use com ninguém usando o sistema);
   - **FECHAR LKI INDUSTRIAL** — desliga o sistema.

## Como chegam as atualizações
1. Cada mudança aprovada na branch `main` passa pelos testes e o GitHub monta um pacote novo para Windows, **testado num Windows real** (instalação, cálculo, DXF, atualização e volta atrás).
2. O pacote é publicado no release `lki-windows`.
3. Quem usa clica em **ATUALIZAR LKI INDUSTRIAL**. O atualizador confere a impressão digital (SHA-256) do pacote, faz backup do banco, troca o programa e, se a versão nova não responder, **volta sozinho** para a anterior com o banco de antes.

## Onde ficam as coisas
`%LOCALAPPDATA%\LkiIndustrial\` (ex.: `C:\Users\NOME\AppData\Local\LkiIndustrial`)

| Pasta/arquivo | Conteúdo |
|---|---|
| `programa\` | versão instalada (Python embutido + sistema). Trocada inteira a cada atualização |
| `programa.anterior\` | versão anterior, para voltar atrás |
| `dados\app.db` | banco de dados (SQLite) |
| `dados\arquivos\` | plantas, fotos e documentos enviados |
| `dados\backups\` | backup diário do banco (ao abrir) e antes de cada atualização |
| `dados\logs\` | registros do servidor e das atualizações |
| `config.env` | configuração local (senhas). **Não compartilhe** |

**Copie `dados\` para outro lugar de vez em quando** (OneDrive, HD externo).

## Acesso pelos outros computadores da rede
Liberado na instalação (opção marcada por padrão) ou depois pelo Menu Iniciar → **LIBERAR REDE LKI INDUSTRIAL**. Nos outros computadores: `http://IP-DESTE-COMPUTADOR:8080` (o IP aparece ao liberar).

Alternativa sem .exe: `INSTALAR-LKI-INDUSTRIAL.cmd` (mesmo link, trocando o nome do arquivo) baixa e instala pelo terminal.

## Limitações
- Banco SQLite: ótimo para um computador e poucos usuários simultâneos. Para muitos usuários ao mesmo tempo, use a instalação com servidor (PostgreSQL) — ver `deploy/LEIAME-SERVIDOR.md`.
- O sistema funciona enquanto o computador estiver ligado e o LKI INDUSTRIAL aberto.
