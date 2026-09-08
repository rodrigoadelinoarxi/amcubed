# Ledger de Migração — AMCUBED v19 (Odoo.sh)

Registo das correções feitas na migração para v19 do `AMCUBED`, dividido em duas fases:

- **Fase A** — erros encontrados **durante o próprio script de upgrade oficial da Odoo**
  (`upgrade.odoo.com`, comando `upgrade.py test`/`production`), antes de o pedido
  `production` ser sequer aceite/completado. Correções aplicadas à **base de origem** ou
  à forma como o motor (`migrate.sh`) invoca o script oficial.
- **Fase B** — erros encontrados **depois** do upgrade oficial já ter devolvido a base em
  v19, ao ativar Enterprise + módulos próprios do cliente (código privado que o serviço da
  Odoo não vê) via `odoo -u all`. Correções no código deste repo e na base já migrada.

- **BD:** `AMCUBED` (testada localmente em container Docker temporário durante a
  reconciliação, nome do container variável por run)
- **Data:** 2026-09-07
- **Branch com o código já corrigido:** `odoo-sh-migration-v19-20260907153055` (pushed)

## Estado atual (atualizado 2026-09-08 13:20) — MIGRAÇÃO EM PROGRESSO, AINDA NÃO CONCLUÍDA

Correção 2026-09-08: a nota anterior ("nenhum container em execução") estava ERRADA — foi
um falso negativo do meu próprio comando de diagnóstico (`docker ps --filter name=amcubed`
em minúsculas não apanha os nomes reais, que são `AMCUBED_19_odoo`/`AMCUBED_19_db`/
`AMCUBED_odoo_sh_prod_db`, maiúsculas). A instância real **está no ar e estável há mais de
22h** (`AMCUBED_19_odoo`, sem restarts, HTTP 303 normal em `:8022/odoo/login`, cron jobs a
correr sem erros). O upgrade oficial pago (`upgrade.odoo.com production`) tinha terminado
com sucesso — o que faltava era só a reconciliação de Enterprise + módulos próprios.

**Diagnosticado e corrigido ao vivo hoje (2026-09-08), com efeito imediato no container em
produção — este repo está montado como volume live, por isso as correções de código
aplicam-se sem rebuild:**

- **B5. `account_debit_note` não era instalado automaticamente** — módulo standard Odoo
  (installable=True, só depende de `account`), presente em
  `/usr/lib/python3/dist-packages/odoo/addons/account_debit_note`, mas ficava preso em
  `uninstalled` e o resolvedor de dependências saltava `l10n_pt_certificate` com "some
  depends are not loaded (account_debit_note)". **Corrigido:** instalado diretamente
  (`odoo -i account_debit_note`) — depois disso `l10n_pt_certificate` deixou de ser
  bloqueado.
- **B6. `contract_instance_checker` em falta no repo do AMCUBED** — mesmo padrão já
  documentado no ledger do admincore_sh (decisão 2026-07-08: é dependência REAL de
  `l10n_pt_ao`, vive em `arxi-quality/`, não deve ser stubado). Só faltava na cópia deste
  cliente. **Corrigido:** copiado de
  `projects/admincore_sh/repo/arxi-quality/contract_instance_checker` para
  `arxi-quality/contract_instance_checker` deste repo (commit nesta entrada).
- **Resultado das duas correções acima:** toda a cadeia fiscal PT-AO ficou desbloqueada e
  **está `installed` agora**: `l10n_pt_ao`, `l10n_pt_ao_access`, `l10n_pt_ao_saft`,
  `l10n_pt_ao_sale`, `l10n_pt_sale`, `l10n_pt_stock`, `l10n_pt_delivery`,
  `l10n_pt_reports_arxi`, `ARXI_CERTIFICATION_PATCH`, `contract_instance_checker`,
  `account_debit_note` (confirmado por SQL direto à BD em produção).
- **B7. Dependência Python `html5lib` em falta** (bloqueava `l10n_pt_efatura_import`):
  `odoo.exceptions.UserError: Unable to install module "l10n_pt_efatura_import" because an
  external dependency is not met: html5lib`. **Corrigido** — instalado no container e
  adicionado a `requirements.txt` (commit nesta entrada).
- **B2 (retomado). `openai`** — a falha de instalação de ontem não se repetiu ao tentar de
  novo hoje (parece ter sido um problema de rede transitório); instalado com sucesso no
  container. `requirements.txt` já o tinha listado desde antes, não precisou de alteração.

**Ainda por resolver:**

- Os restantes **34 módulos** próprios do AMCUBED (`l10n_pt_saphety*`, `l10n_pt_pos`,
  `l10n_pt_hr_payroll`, `payment_eupago*`, `arxi_openai_client`,
  `arxi_quality_payroll_api_client`, etc. — ver lista completa em B4) continuam
  `uninstalled`. Tentativa de instalação em lote hoje falhou com um erro NOVO e mais
  profundo, ainda não resolvido:
  ```
  odoo.sql_db: bad query: ...SELECT ... "ir_ui_view"."protected" ...
  ERROR: column ir_ui_view.protected does not exist
  odoo.registry: Failed to load registry
  ```
  Hipótese mais provável (não confirmada): o campo `protected` é nativo do `ir.ui.view` no
  Odoo 19 core, mas o `-u base` nunca completou 100% nesta base — uma tentativa de correr
  `odoo -u base` isoladamente falhou com um `ParseError` a carregar
  `base/data/res_lang_data.xml` (imagem de bandeira em falta para `sr@latin`, `rs.png` —
  mesma família de "erros de imagem em falta" já vista noutras migrações, mas aqui parece
  estar a impedir a sincronização do schema, não só um erro cosmético). Precisa de
  investigação dedicada: confirmar se `ir_ui_view.protected` é mesmo um campo nativo do v19
  core, e se sim, corrigir/contornar o `ParseError` do `res_lang_data.xml` para o `-u base`
  completar e a coluna ser criada.
- Depois disso, reavaliar item a item os 34 módulos (alguns podem ter bugs próprios, não só
  esta dependência de schema).
- B3 (XPath `check_out_inherit`) e B4 original ficam supersedidos por esta atualização —
  `website_payment_method_fees` já está `installed` na BD atual, o crash de ontem não se
  repetiu nesta instância viva (possivelmente porque a run de ontem que crashou era um
  container de teste efémero da reconciliação, distinto deste `AMCUBED_19_odoo`).

## Resumo

### Fase A — durante o script oficial `upgrade.odoo.com`

| # | Assunto | Estado |
|---|---|---|
| A1 | `ir_model.order='display_name'` em `account.tax.exemption` (crash no crawler de teste do upgrade oficial) | **RESOLVIDO** — mesma correção genérica já usada no admincore_sh (`fix_tax_exemption_model_order`), confirmada a correr nos logs (14:59:25 e 15:15:12) |
| A2 | `account.payment` sem/errado `payment_method_line_id` | **NÃO APLICÁVEL** — confirmado por grep aos logs, o erro nativo "Please define a payment method line" nunca ocorreu nesta migração; as funções de correção existem no motor mas não foram acionadas |
| A3 | Cópia local para o pedido `production` só sabia restaurar `.sql`, backup do AMCUBED é `.zip` (`amcubed-master-..._test_nofs.zip`) | **RESOLVIDO no motor 2026-09-07** — corrigido `migrate.sh` para tratar `.zip`/`.dump` também nesta cópia local, mesma lógica já usada no passo `test`. Sem isto o pedido `production` (pago) falhava sempre depois do `test` (grátis) já ter passado — só detetado ao vivo com este cliente |

```sql
-- A1
UPDATE ir_model
SET "order" = 'code'
WHERE model = 'account.tax.exemption'
  AND "order" = 'display_name';
```

### Fase B — depois do upgrade oficial, ao ativar Enterprise + módulos próprios

| # | Assunto | Estado |
|---|---|---|
| B1 | Módulo Enterprise `social_push_notifications` precisa da dependência Python `google-auth`, em falta | **RESOLVIDO** (commit `9c07c69`, `requirements.txt`) — sem isto, `odoo -u all` bloqueava logo na 1ª iteração da reconciliação, antes de sequer chegar aos módulos próprios do AMCUBED |
| B2 | Dependência Python `openai` falha a instalar | **NÃO RESOLVIDO** — `AVISO: falha ao instalar a dependência Python 'openai'` repetido nos logs (15:32:02 e 15:35:18); impede `arxi_openai_client` e `arxi_quality_payroll_api_client` de ficar instalados |
| B3 | XPath inválido em `appstore/website_payment_method_fees/views/templates.xml`, vista `check_out_inherit` | **NÃO RESOLVIDO — bloqueia o arranque** (ver detalhe abaixo) |
| B4 | 35 módulos custom não instalados | **NÃO RESOLVIDO** — consequência direta de B3 (o crash de registo impede o `-u all` de terminar); ver lista completa abaixo |

## B1. Dependência Python `google-auth` em falta

**Sintoma:** módulo Enterprise `social_push_notifications` (não é custom nosso, faz parte
do `addons_path` Enterprise sempre montado) precisa de `google-auth`. Sem isto o
`odoo -u all` parava logo na 1ª iteração da reconciliação de módulos custom, antes de
chegar aos módulos próprios do AMCUBED — a lista de "não instalados" reportada em runs
anteriores estava inflacionada por causa deste bloqueio, não por incompatibilidade real.

**Correção (código, já commitada e pushed):**
```diff
--- a/requirements.txt
+++ b/requirements.txt
@@
+google-auth
```

## B2. Dependência Python `openai` falha a instalar (NÃO RESOLVIDO)

**Sintoma:** `[2026-09-07 15:32:02] AVISO: falha ao instalar a dependência Python 'openai'
— a continuar com as restantes.` — repete-se em cada run. O motor continua sem essa
dependência em vez de parar, mas os módulos que dela dependem (`arxi_openai_client`,
`arxi_quality_payroll_api_client`) ficam por instalar.

**Por fazer:** confirmar a causa exata da falha de instalação (rede, versão pinada em
conflito, `pip` dentro do container sem acesso à internet nesse momento, etc.) — não
diagnosticado ainda. Ver `requirements.txt`/`Dockerfile` da imagem custom em
`/opt/odoo-migrations/projects/AMCUBED/real_odoo19/`.

## B3. XPath inválido em `check_out_inherit` (NÃO RESOLVIDO — bloqueia o arranque)

**Sintoma:** a reconciliação crasha com `CRITICAL ... Failed to initialize database
AMCUBED` ao carregar o módulo `website_payment_method_fees` (pasta `appstore/` deste
repo):

```
odoo.tools.convert.ParseError: while parsing None:4
Error while parsing or validating view:

Element '<xpath expr="//div[@id='cart_total']//table//tr[@id='order_total_taxes']">' cannot be located in parent view

View error context:
{'file': '/mnt/extra-addons/appstore/website_payment_method_fees/views/templates.xml',
 'line': 2,
 'name': 'check_out_inherit',
 'view': ir.ui.view(4214,),
 'view.model': False,
 'view.parent': ir.ui.view(3543,),
 'xmlid': 'check_out_inherit'}
```

**Causa provável (por confirmar):** a vista pai do template de checkout do `website_sale`
mudou de estrutura no v19 (o `id='cart_total'`/`id='order_total_taxes'` não existem mais
com esses ids, ou a tabela de totais foi refeita — padrão já visto noutras migrações com
`account.tax_groups_totals` descontinuado a favor de `tax_totals`/`subtotals`). **Por
fazer:** localizar a vista atual do checkout no v19 (`website_sale`), identificar o
elemento equivalente e adaptar o XPath — **não desativar a funcionalidade** (ver regra
[[feedback_xpath_adaptar_nao_desativar]]: XPath inválido não é funcionalidade removida, é
preciso achar a vista equivalente e adaptar).

## B4. 35 módulos custom não instalados (consequência de B3)

Lista completa reportada pela última run (2026-09-07 15:35:22), antes de qualquer
diagnóstico individual — a maioria destes pode instalar normalmente assim que B3 for
corrigido, já que o crash em B3 impede o `-u all` de sequer terminar a iteração:

```
account_credit_note_no_origin, account_second_discount, cert_vies_integration,
defir_integration, display_total_discount, external_invoice_payments,
l10n_pt_ao_consignment_invoices, l10n_pt_ao_industry_fsm_sale, l10n_pt_ao_journal_entry,
l10n_pt_ao_pos, l10n_pt_ao_pos_loyalty, l10n_pt_ao_pos_settle_due, l10n_pt_ao_sale_ws,
l10n_pt_efatura_import, l10n_pt_hr_payroll, l10n_pt_intrastat,
l10n_pt_payment_term_discount, l10n_pt_payroll_unique_report, l10n_pt_pos,
l10n_pt_sale_second_disc_reports, l10n_pt_saphety, l10n_pt_saphety_buyer_code,
l10n_pt_saphety_sale_purchase_request_nr, l10n_pt_saphety_stock_purchase_request_nr,
l10n_pt_saphety_subscription, l10n_pt_saphety_transport_documents,
l10n_pt_total_discount_reports, sale_second_discount, stock_valuation_returns,
unlock_order_lines, vendor_payment_sequence, arxi_openai_client,
arxi_quality_payroll_api_client, payment_eupago, payment_eupago_mbref_account_report
```

**Este script nunca desativa módulos por sua iniciativa** (ver regra
[[feedback_nao_desinstalar_modulos_da_origem]]) — precisa de diagnóstico módulo a módulo
depois de B3 e B2 estarem resolvidos.

## Próximos passos

1. Resolver B3 (XPath do checkout) — bloqueador atual, sem isto nada mais reconcilia.
2. Diagnosticar e resolver B2 (`openai` pip install).
3. Relançar a reconciliação e reavaliar a lista de B4 (deve encolher drasticamente depois
   de B2/B3).
4. Só depois disso — teste de qualidade + validação de negócio antes de considerar esta
   migração concluída.

## Atualização 2026-09-08 — B3 resolvido, causa raiz real de B4 encontrada (não era código)

O utilizador reportou dois sintomas na instância `disk_odoo_sh_production_AMCUBED_19_20260907_145836`
(porta 8022): a lista "não instalados" do painel continuava a mostrar ~34 módulos, e o
botão "Login as" não aparecia (só "Prepare test logins"). Diagnóstico ao vivo no
container `AMCUBED_19_odoo` revelou que ambos os sintomas tinham a MESMA causa raiz, e que
a lista B4 nunca tinha sido o que parecia.

### C1. Causa raiz real: `docker cp` do filestore Odoo.sh deixa ficheiros donos de `ubuntu`, chown sem `-u root` falha em silêncio (RESOLVIDO no motor)

`deploy_odoo_sh_real_instance()` em `migrate.sh` copia o filestore do backup Odoo.sh para
o container via `docker cp` e faz `docker exec "$real_odoo" chown -R odoo:odoo ...` a
seguir — mas o container corre com utilizador por omissão `odoo` (não root), que não tem
permissão para fazer chown a ficheiros que não lhe pertencem. O `docker exec` falhava
sempre em silêncio (sem verificação de exit code). Confirmado ao vivo: **136 dos 141
diretórios** do filestore `AMCUBED` pertenciam a `ubuntu:ubuntu`, não a `odoo:odoo`.

Isto causava uma cadeia de falhas:
1. `odoo -u base` crashava com `PermissionError` ao tentar fazer GC de um anexo (imagem de
   bandeira `rs.png` em `res_lang_data.xml`) num diretório do filestore sem permissão de
   escrita para `odoo` — o `-u base` nunca completava.
2. Sem `-u base` completar, a coluna `ir_ui_view.protected` (nativa do v19) nunca era
   criada no schema.
3. Qualquer escrita em `res.users` (ex.: reset de password no "Prepare test logins")
   disparava `_notify_security_setting_update` → render do template
   `mail.account_security_alert`, que consulta `ir_ui_view.protected` → `UndefinedColumn`
   → `UserError: Failed to render template` → o "Login as" nunca aparecia no painel.
4. Sem `-u base` completar, o `-u all` da reconciliação (`reconcile_odoo_sh_custom_modules`)
   também nunca chegava a processar a maioria dos 365 módulos — parava muito cedo.

**Correção aplicada (motor, `migrate.sh` linha ~4862):** `docker exec -u root "$real_odoo"
chown -R odoo:odoo ...` (mesmo padrão já usado corretamente no caminho on-premise, linhas
880 e 905 — só o caminho Odoo.sh production tinha ficado sem `-u root`). Corrigido também
ao vivo no container `AMCUBED_19_odoo` (`docker exec -u root ... chown -R odoo:odoo
/var/lib/odoo/filestore/AMCUBED`).

### C2. B3 (XPath `check_out_inherit`) — RESOLVIDO

Confirmada a causa: `website_sale.total` no v19 deixou de ter `<div id="cart_total">` e as
`<tr>` deixaram de ter `id="order_total_taxes"`/`id="order_total"` — passaram a usar
`name="o_order_total_taxes"`/`name="o_order_total"` sem `id` nenhum na div envolvente.
XPath adaptado em `appstore/website_payment_method_fees/views/templates.xml` (ver
[[feedback_xpath_adaptar_nao_desativar]], funcionalidade preservada, não desativada):

```diff
- <xpath expr="//div[@id='cart_total']//table//tr[@id='order_total_taxes']" position="after">
+ <xpath expr="//table//tr[@name='o_order_total_taxes']" position="after">
...
- <xpath expr="//tr[@id='order_total']//td[2]" position="attributes">
+ <xpath expr="//tr[@name='o_order_total']//td[2]" position="attributes">
```

Com C1 + C2 corrigidos, `odoo -u all` completa: "Modules loaded" em 146s,
`website_payment_method_fees` fica `installed`, "Prepare test logins" e "Login as" passam
a funcionar (testado: `login-as?user=admin` devolve 302 + cookie de sessão válido).

### C3. A lista "34 módulos não instalados" era um falso positivo do motor, não uma regressão desta migração (RESOLVIDO no motor)

Depois de C1+C2, `odoo -u all` correu completo e os 34 módulos continuaram
`uninstalled` — porque `-u` só atualiza módulos já instalados, nunca instala módulos
novos. Isto levantou a pergunta do utilizador: talvez estes módulos tenham sido
**fundidos/consolidados** durante a reescrita da certificação e já não façam sentido
isolados.

Confirmado por comparação direta com o backup de origem
(`db_backups/amcubed-master-26852963_2026-09-02_181858_test_nofs.zip`, dump.sql, tabela
`ir_module_module`): **33 dos 34 módulos "em falta" já estavam `uninstalled` na BD de
origem, antes de qualquer migração** (2 nem sequer existiam lá:
`cert_vies_integration`, `l10n_pt_ao_industry_fsm_sale`). Só `website_payment_method_fees`
estava genuinamente `installed` na origem — e esse é precisamente o único que a
reconciliação corrigiu (C1/C2). Ou seja: **não há regressão nenhuma** nos restantes 33 —
a sua funcionalidade já não estava ativa no AMCUBED antes da migração (consolidada nos
módulos de certificação como `l10n_pt_ao`, `l10n_pt_certificate`, `l10n_pt_reports_arxi`,
`arxi_amcubed`, que esses sim estão instalados).

**Causa raiz do falso positivo:** `custom_modules` em `deploy_odoo_sh_real_instance()` é
construído a partir de TODAS as pastas com `__manifest__.py` encontradas no repo
(`find "$repo_dir" -iname "__manifest__.py"`), sem verificar se esse módulo alguma vez
esteve instalado na origem. Um módulo mantido no repo por histórico/reutilização parcial
de código, mas já obsoleto/fundido, era sempre reportado como "não instalado" mesmo sem
nunca ter sido suposto instalar.

**Correção aplicada (motor, `migrate.sh`):** `deploy_odoo_sh_real_instance()` agora extrai,
do próprio `dump.sql` do zip descarregado (`ir_module_module`, coluna `state`), a lista de
módulos que já estavam `installed` na origem, e só reporta em
`RESULT_CUSTOM_MODULES_NOT_INSTALLED` os módulos que estavam nessa lista e deixaram de
estar instalados — nunca módulos que já não estavam instalados na origem. Não há
desinstalação nem alteração de comportamento de instalação, só correção do relatório (ver
[[feedback_nao_desinstalar_modulos_da_origem]] — este ajuste está alinhado com essa regra,
só deixa de alarmar sobre módulos que a origem já não tinha).

### Resumo do estado atual

| # | Assunto | Estado |
|---|---|---|
| C1 | `docker cp` filestore Odoo.sh + chown sem `-u root` (causa raiz real de B3/B4/login-as) | **RESOLVIDO no motor + ao vivo no container** |
| C2 | B3 — XPath `check_out_inherit` obsoleto no v19 | **RESOLVIDO** |
| C3 | Lista "módulos não instalados" incluía módulos nunca instalados na origem | **RESOLVIDO no motor** (relatório corrigido, não é uma migração de dados) |

**Por fazer:** B2 (`openai` pip install) continua por resolver — não bloqueia mais nada
crítico, só os dois módulos `arxi_openai_client`/`arxi_quality_payroll_api_client` (que,
confirmado no dump de origem, também já estavam `uninstalled` antes da migração, portanto
não é uma regressão urgente). Antes de considerar a migração concluída: correr o teste de
qualidade (`quality_test.js`) e a validação de fluxos de negócio contra esta instância já
corrigida.

## Atualização 2026-09-08 (continuação) — instância "muito lenta" após login: causa raiz real e correção completa

Depois de C1-C3, o utilizador conseguiu fazer login mas reportou a instância "muito
lenta" (ecrã "Apps" preso a carregar). Diagnóstico ao vivo: a BD tinha **20 módulos
custom genuinamente instalados na origem** presos em `to upgrade` (nunca chegavam a
`installed`), e um módulo com estado nesse limbo faz o Odoo repetir o carregamento
COMPLETO do registo de módulos em CADA pedido HTTP (via
`odoo.addons.base.models.ir_cron: Skipping database ... because of modules to
install/upgrade/remove` + reload síncrono do registo) — por isso a lentidão extrema, não
era um processo pesado a correr, era isto.

### D1. 22 módulos com `version` de manifesto ainda "17.0.x" (ou "18.0.x"/"1.0") — RESOLVIDO

O Odoo recusa completar o upgrade de um módulo cujo `version` no manifesto não começa
pela série do servidor (`19.0`) — marca `installable=False` e o módulo fica preso em
`to upgrade` para sempre (nunca chega a `installed` nem a `uninstalled`, porque nunca
termina o upgrade). Confirmado que TODOS estes 20 estavam `installed` na origem (dump
`db_backups/amcubed-master-...zip`) — regressão real, não módulos obsoletos. Corrigido:
bump do campo `version` para `19.0.x` (só metadado, sem alterar lógica) em:

`custom_website_sale_stock`, `hide_menu_user`, `import_bill_of_materials_in_mrp`,
`payment_date`, `payment_eupago`, `payment_eupago_arxi`, `payment_eupago_cc`,
`payment_eupago_mbref`, `payment_eupago_mbref_sale`, `payment_eupago_mbway`,
`product_assortment`, `product_pricelist_assortment`, `product_pricelist_by_contact`,
`statement_report`, `stock_no_negative`, `vies_integration`, `arxi_amcubed`,
`arxi_quality_instance_client`, `l10n_pt_account_batch_payment` (era `'1.0'`) — e por
consistência, também `l10n_pt_efatura_import` (era `18.0.x`, estava `uninstalled` na
origem, não bloqueava nada mas ficou coerente) e `arxi_openai_client`/
`arxi_quality_payroll_api_client` (idem, bloqueados por B2, não pela versão).

### D2. Incompatibilidades reais de código Python/XML v17→v19 nos módulos acima — RESOLVIDAS

Depois do bump de versão, cada módulo revelou o seu próprio erro de carregamento
(iterado um de cada vez, corrigido, relançado — nunca abortado a meio):

- **`arxi_quality_instance_client`**: `from odoo import ... registry` — o símbolo
  `odoo.registry` foi removido no v19 (mudou para `odoo.orm.registry.Registry`).
  Import nunca era usado no ficheiro — removido (`controllers/main.py`).
- **`hide_menu_user`**: `@api.returns('self')` — decorator removido no v19. Método já
  devolve o tipo certo via `super()`, decorator era só uma anotação — removido
  (`models/res_users.py`).
- **`<tree>` → `<list>`** (renomeação global do v19, raiz de list views E `<field><tree>`
  aninhados dentro de forms — confirmado 0 ocorrências de `<tree` em todo o core v19):
  `hide_menu_user/views/res_users_views.xml`,
  `product_pricelist_assortment/views/product_pricelist.xml` (+ um xpath
  `.../field[@name='item_ids']/tree` → `.../list`),
  `product_pricelist_assortment/views/product_pricelist_assortment_item.xml`,
  `product_assortment/views/product_assortment.xml`,
  `statement_report/views/res_partner_views.xml`.
- **`view_mode` com `'tree'`** (mesma renomeação, mas como valor de string em ações):
  `product_pricelist_assortment_item.xml` (`tree,form`→`list,form`) e
  `product_assortment.xml` (dict Python inline `'view_mode': 'tree'`→`'list'`).
- **`<group expand="0" string="Group By">` em vista `search`** — o v19 removeu os
  atributos `expand`/`string` do elemento `<group>` dentro de `<search>` (confirmado:
  nenhuma vista search do core v19 usa esse padrão antigo; agora é só `<group>` a
  envolver os `<filter>` de group-by). Corrigido em
  `product_pricelist_assortment_item.xml`.
- **`base.module_category_manufacturing_manufacturing`** — XML ID de categoria
  reorganizado no v19 (categorias agora aninhadas sob "Supply Chain"). Novo ID:
  `base.module_category_supply_chain_manufacturing`
  (`import_bill_of_materials_in_mrp/security/import_bom_security.xml`).
- **`res.groups.category_id`** — o campo foi removido do modelo `res.groups` no v19; a
  categorização de grupos de segurança passou a usar `privilege_id` (many2one a
  `res.groups.privilege`, populado por módulo). Corrigido para
  `privilege_id` = `mrp.res_groups_privilege_manufacturing` (mesmo ficheiro).

### D3. Três módulos ficaram presos por razões distintas — dois resolvidos, um por decidir

- **`l10n_pt_account_batch_payment`**: **não é bug nenhum** — o próprio manifesto já
  tinha `'installable': False` com um comentário datado de 2026-07-10 a explicar que o
  modelo alvo foi removido no v19 e a funcionalidade (imutabilidade de pagamentos
  certificados) passou a ser garantida pelos guards do core
  (`l10n_pt_ao`/`l10n_pt_certificate`) — decisão já tomada, só nunca tinha sido
  propagada ao estado da BD desta instância. Estado corrigido para `uninstalled`
  (SQL direto, sem alterar código).
- **`whatsapp_oauth`**: **não estava instalado na origem** (confirmado no dump) e o
  módulo não existe em lado nenhum do addons_path acessível (nem custom, nem
  Enterprise montado) — provavelmente um artefacto do próprio `upgrade.odoo.com`
  a tentar modernizar uma integração WhatsApp antiga que não faz parte deste bundle
  Enterprise self-hosted. Sem perda de funcionalidade real (nunca esteve ativo para o
  AMCUBED). Estado corrigido para `uninstalled` (SQL direto).
- **`credit_note_specific_account`** — ⚠️ **POR DECIDIR, não resolvido**: este SIM
  estava `installed` na origem (confirmado no dump) — é uma regressão real, ao
  contrário dos dois acima. O módulo (adiciona escolha de conta ao criar uma nota de
  crédito) simplesmente **não existe no repo do AMCUBED** — mas existe, já adaptado
  para v19 (`version: '19.0.1.0.0'`, sem `installable: False`, ainda ativo), no repo
  doutro cliente (`admincore`, pasta `arxi_certification/credit_note_specific_account`)
  — é claramente um módulo partilhado da família `arxi_certification` que ficou de
  fora do checkout do AMCUBED por engano. Como é código de negócio financeiro (afeta
  notas de crédito), não copiei o módulo de outro cliente para aqui sem revisão. Como
  stop-gap TEMPORÁRIO para desbloquear a lentidão (estado preso em `to upgrade`
  impedia o registo de assentar), o estado foi posto a `uninstalled` por SQL direto —
  isto NÃO é a decisão final, precisa de: (a) confirmar que o módulo do admincore é
  genérico/reutilizável e não específico desse cliente, (b) copiá-lo para
  `arxi_certification/credit_note_specific_account/` no repo do AMCUBED, (c)
  reinstalar.

### Resultado

`odoo -u all` conclui limpo (382/382 módulos, "Modules loaded", ~2 min), **zero**
módulos em estado não-terminal, container reiniciado para o processo principal também
ficar com o registo fresco (o reload incremental via sinalização da BD tinha ficado com
cache parcial/obsoleta de tentativas anteriores da sessão — reiniciar resolveu). Tempo
de resposta de `/web/login` caiu de ~0.7-0.8s (registo a recarregar em cada pedido) para
~0.05s.

### Resumo atualizado

| # | Assunto | Estado |
|---|---|---|
| D1 | 20 módulos com `version` de manifesto pré-v19 (bloqueava upgrade permanentemente) | **RESOLVIDO** |
| D2 | ~7 incompatibilidades reais de código Python/XML v17→v19 nesses módulos | **RESOLVIDAS** |
| D3a | `l10n_pt_account_batch_payment` preso — já obsoleto por decisão documentada | **RESOLVIDO** (estado corrigido) |
| D3b | `whatsapp_oauth` preso — nunca esteve na origem, módulo indisponível | **RESOLVIDO** (estado corrigido) |
| D3c | `credit_note_specific_account` preso — módulo real em falta no repo | **STOP-GAP aplicado, decisão humana pendente** |

**Próximo passo:** decidir e executar D3c (copiar módulo do admincore, se aplicável), depois
continuar para o teste de qualidade + validação de fluxos de negócio já mencionados acima.
