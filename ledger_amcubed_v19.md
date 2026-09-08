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

## Estado atual — MIGRAÇÃO NÃO CONCLUÍDA

A última run (logs `AMCUBED_odoo_sh_production_19_20260907_145836.log` /
`AMCUBED_odoo_sh_upgrade_19_20260907_145836.log`, terminada 2026-09-07 15:35) **parou**
durante a reconciliação de módulos custom, com um erro real de vista (B3, por resolver) e
**35 módulos custom por instalar**. Não há atualmente nenhum container Docker do AMCUBED
em execução (`docker ps -a --filter name=amcubed` vazio) — o trabalho ficou por retomar.

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
