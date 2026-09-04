-- activate neutralization watermarks
UPDATE res_company
   SET saphety_test_env = true
 WHERE saphety_integration = true;
