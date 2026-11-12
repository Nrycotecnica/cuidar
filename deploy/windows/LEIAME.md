# LKI INDUSTRIAL para Windows — instalador de um arquivo só

Forma recomendada de instalar no computador de quem vai usar: **não precisa de Docker, nem de administrador, nem reiniciar.**

## Para quem vai instalar
1. Baixe **`INSTALAR-LKI-INDUSTRIAL.cmd`**:
   https://github.com/Nrycotecnica/cuidar/releases/download/lki-windows/INSTALAR-LKI-INDUSTRIAL.cmd
2. Dê **dois cliques** no arquivo.
   - Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações → Executar assim mesmo** (o arquivo não tem assinatura digital paga).
3. Aguarde o download (≈ 100–150 MB) e crie o **e-mail e a senha** do administrador.
4. Pronto: o navegador abre em **http://127.0.0.1:8080**. Na Área de Trabalho ficam três atalhos:
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
Por padrão o sistema só atende o próprio computador. Para liberar na rede local: em `config.env` mude `REDE=0` para `REDE=1`, feche e abra pelo atalho, e permita o acesso quando o Firewall do Windows perguntar (pede administrador). Depois, nos outros computadores: `http://IP-DESTE-COMPUTADOR:8080`.

## Limitações
- Banco SQLite: ótimo para um computador e poucos usuários simultâneos. Para muitos usuários ao mesmo tempo, use a instalação com servidor (PostgreSQL) — ver `deploy/LEIAME-SERVIDOR.md`.
- O sistema funciona enquanto o computador estiver ligado e o LKI INDUSTRIAL aberto.
