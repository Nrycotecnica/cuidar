# Cancelar a hospedagem no Render

Os recursos foram criados pelo Blueprint `lki-industrial`. Segundo a documentação do Render, **um recurso apagado manualmente é recriado na próxima sincronização do Blueprint** — por isso siga esta ordem. (Passos conferidos em render.com/docs em 12/11/2026; os nomes dos botões podem mudar.)

Os dados atuais no Render são só de teste: a homologação tem os projetos demonstrativos e a produção está vazia. **Se você já cadastrou algo que queira guardar, avise antes** — o Render não guarda backup de banco apagado.

1. **Desligar a sincronização automática**
   Painel do Render → **Blueprints** → `lki-industrial` → **Settings** → **Auto Sync: No**.
   (O arquivo `render.yaml` também foi retirado do repositório, para não recriar nada.)

2. **Apagar os serviços web** (param de cobrar a partir daí; a cobrança é proporcional ao tempo)
   - `lki-homologacao` → **Settings** → no final da página, **Delete Web Service** → confirme digitando o nome.
   - `lki-producao` → idem.
   Os discos (`arquivos`) são apagados junto com cada serviço.

3. **Apagar os bancos**
   - `lki-db-homologacao` → página **Info** → no final, **Delete Database**.
   - `lki-db-producao` → idem.

4. **Apagar o Blueprint / projeto**
   - **Blueprints** → `lki-industrial` → **Settings** → excluir o Blueprint.
   - Se o projeto `lki-industrial` continuar listado em **Projects**, exclua-o também (vazio, não gera custo).

5. **Conferir a cobrança**
   - **Workspace Settings → Billing**: confira que não restou nenhum serviço ativo. A fatura do mês trará apenas o tempo em que os recursos ficaram ligados.
   - Se quiser, remova o cartão em **Billing → Payment methods**.

6. **Opcional — desconectar o GitHub do Render**
   No GitHub: **Settings → Applications → Installed GitHub Apps → Render → Configure → Uninstall** (ou remova só o repositório `cuidar`).
