-- activate neutralization for AT websevice
UPDATE res_company
   SET at_test = true
 WHERE at_gt_active = true;
