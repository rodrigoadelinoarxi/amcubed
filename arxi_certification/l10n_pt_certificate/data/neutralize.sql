-- activate neutralization watermarks
UPDATE res_company
   SET l10n_pt_at_test = true
 WHERE l10n_pt_at_webservice = true;