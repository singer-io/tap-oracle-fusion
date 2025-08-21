# tap-oracle-fusion

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/docs/SPEC.md).

This tap:

- Pulls raw data from the [Oracle-fusion API].
- Extracts the following resources:
    - [BankAccounts](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashbankaccounts-get.html)

    - [CashBankAccountDff](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/api-bank-accounts-bank-account-descriptive-flexfields.html)

    - [BankAccountPaymentDocuments](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashbankaccounts-bankaccountid-child-bankaccountpaymentdocuments-get.html)

    - [CashBankBranches](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashbankbranches-get.html)

    - [Cashbanks](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashbanks-get.html)

    - [BrazilianFiscalDocuments](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-brazilianfiscaldocuments-get.html)

    - [CashPools](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashpools-get.html)

    - [CashPoolMembers](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashpools-cashpoolid-child-cashpoolmembers-get.html)

    - [CollectionStrategies](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-collectionstrategies-get.html)

    - [Tasks](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-collectionstrategies-strategyid-child-strategyexecutiontasks-get.html)

    - [CurrencyRates](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-currencyrates-get.html)

    - [DataSecurities](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-datasecurities-get.html)

    - [DebitAuthorizations](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-debitauthorizations-get.html)

    - [Erpintegrations](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-erpintegrations-get.html)

    - [Expenses](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-expenses-get.html)

    - [ExpensesAttachments](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-expenses-expensesuniqid-child-attachments-get.html)

    - [ExternalBankAccounts](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-externalbankaccounts-get.html)

    - [AccountOwners](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-externalbankaccounts-bankaccountid-child-accountowners-get.html)

    - [FedGroups](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-fedgroups-get.html)

    - [FedGroupBudgetLevels](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-fedgroups-ledgergroupid-child-fedgroupbudgetlevels-get.html)

    - [Invoices](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-invoices-get.html)

    - [Invoice](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-invoices-invoicesuniqid-get.html)

    - [JointVentures](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-jointventures-get.html)

    - [Messages](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-jointventures-jointventureid-child-messages-get.html)

    - [Stakeholders](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-jointventures-jointventureid-child-stakeholders-get.html)

    - [PayablesPayments](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-payablespayments-get.html)

    - [RelatedInvoices](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-payablespayments-checkid-child-relatedinvoices-get.html)

    - [ReceivablesInvoices](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-receivablesinvoices-get.html)

    - [Attachments](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-receivablesinvoices-customertransactionid-child-attachments-get.html)

    - [Notes](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-receivablesinvoices-customertransactionid-child-notes-get.html)

    - [TaxExemptions](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-taxexemptions-get.html)

    - [TaxRegistrations](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-taxregistrations-get.html)

- Outputs the schema for each resource
- Incrementally pulls data based on the input state


## Streams


**[bank_accounts](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashbankaccounts-get.html)**
- Data Key = items
- Primary keys: ['BankAccountId']
- Replication strategy: INCREMENTAL

**[cash_bank_account_dff](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/api-bank-accounts-bank-account-descriptive-flexfields.html)**
- Data Key = items
- Primary keys: ['BankAccountId']
- Replication strategy: FULL_TABLE

**[bank_account_payment_documents](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashbankaccounts-bankaccountid-child-bankaccountpaymentdocuments-get.html)**
- Data Key = items
- Primary keys: ['PaymentDocumentId']
- Replication strategy: INCREMENTAL

**[cash_bank_branches](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashbankbranches-get.html)**
- Data Key = items
- Primary keys: ['BankPartyId']
- Replication strategy: FULL_TABLE

**[cashBanks](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashbanks-get.html)**
- Data Key = items
- Primary keys: ['BankPartyId']
- Replication strategy: INCREMENTAL

**[brazilian_fiscal_documents](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-brazilianfiscaldocuments-get.html)**
- Data Key = items
- Primary keys: ['DocumentRelationId']
- Replication strategy: FULL_TABLE

**[cash_pools](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashpools-get.html)**
- Data Key = items
- Primary keys: ['CashPoolId']
- Replication strategy: INCREMENTAL

**[cash_pool_members](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-cashpools-cashpoolid-child-cashpoolmembers-get.html)**
- Data Key = items
- Primary keys: ['CashPoolMemberId']
- Replication strategy: INCREMENTAL

**[collection_strategies](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-collectionstrategies-get.html)**
- Data Key = items
- Primary keys: ['StrategyId']
- Replication strategy: INCREMENTAL

**[tasks](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-collectionstrategies-strategyid-child-strategyexecutiontasks-get.html)**
- Data Key = items
- Primary keys: ['WorkItemId']
- Replication strategy: INCREMENTAL

**[currency_rates](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-currencyrates-get.html)**
- Data Key = items
- Primary keys: []
- Replication strategy: FULL_TABLE

**[data_securities](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-datasecurities-get.html)**
- Data Key = items
- Primary keys: ['UserRoleDataAssignmentId']
- Replication strategy: FULL_TABLE

**[debit_authorizations](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-debitauthorizations-get.html)**
- Data Key = items
- Primary keys: ['DebitAuthorizationReferenceNumber']
- Replication strategy: FULL_TABLE

**[erpintegrations](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-erpintegrations-get.html)**
- Data Key = items
- Primary keys: []
- Replication strategy: FULL_TABLE

**[expenses](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-expenses-get.html)**
- Data Key = items
- Primary keys: ['ExpenseId']
- Replication strategy: FULL_TABLE

**[expenses_attachments](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-expenses-expensesuniqid-child-attachments-get.html)**
- Data Key = items
- Primary keys: ['AttachedDocumentId']
- Replication strategy: FULL_TABLE

**[external_bank_accounts](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-externalbankaccounts-get.html)**
- Data Key = items
- Primary keys: ['BankAccountNumber']
- Replication strategy: FULL_TABLE

**[account_owners](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-externalbankaccounts-bankaccountid-child-accountowners-get.html)**
- Data Key = items
- Primary keys: ['AccountOwnerId']
- Replication strategy: FULL_TABLE

**[fed_groups](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-fedgroups-get.html)**
- Data Key = items
- Primary keys: ['LedgerGroupId']
- Replication strategy: INCREMENTAL

**[fed_group_budget_levels](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-fedgroups-ledgergroupid-child-fedgroupbudgetlevels-get.html)**
- Data Key = items
- Primary keys: ['GroupBeLevelId']
- Replication strategy: INCREMENTAL

**[invoices](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-invoices-get.html)**
- Data Key = items
- Primary keys: ['InvoiceId']
- Replication strategy: FULL_TABLE

**[invoice](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-invoices-invoicesuniqid-get.html)**
- Data Key = items
- Primary keys: ['InvoiceId']
- Replication strategy: FULL_TABLE

**[joint_ventures](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-jointventures-get.html)**
- Data Key = items
- Primary keys: ['jointVentureId']
- Replication strategy: INCREMENTAL

**[messages](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-jointventures-jointventureid-child-messages-get.html)**
- Data Key = items
- Primary keys: []
- Replication strategy: FULL_TABLE

**[stakeholders](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-jointventures-jointventureid-child-stakeholders-get.html)**
- Data Key = items
- Primary keys: ['stakeholderId']
- Replication strategy: INCREMENTAL

**[payables_payments](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-payablespayments-get.html)**
- Data Key = items
- Primary keys: ['PaymentId']
- Replication strategy: INCREMENTAL

**[related_invoices](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-payablespayments-checkid-child-relatedinvoices-get.html)**
- Data Key = items
- Primary keys: ['InvoicePaymentId']
- Replication strategy: INCREMENTAL

**[receivables_invoices](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-receivablesinvoices-get.html)**
- Data Key = items
- Primary keys: ['CustomerTransactionId']
- Replication strategy: FULL_TABLE

**[attachments](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-receivablesinvoices-customertransactionid-child-attachments-get.html)**
- Data Key = items
- Primary keys: []
- Replication strategy: FULL_TABLE

**[notes](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-receivablesinvoices-customertransactionid-child-notes-get.html)**
- Data Key = items
- Primary keys: []
- Replication strategy: FULL_TABLE

**[tax_exemptions](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-taxexemptions-get.html)**
- Data Key = items
- Primary keys: ['TaxExemptionId']
- Replication strategy: FULL_TABLE

**[tax_registrations](https://docs.oracle.com/en/cloud/saas/financials/25c/farfa/op-taxregistrations-get.html)**
- Data Key = items
- Primary keys: ['RegistrationId']
- Replication strategy: FULL_TABLE



## Authentication

## Quick Start

1. Install

    Clone this repository, and then install using setup.py. We recommend using a virtualenv:

    ```bash
    > virtualenv -p python3 venv
    > source venv/bin/activate
    > python setup.py install
    OR
    > cd .../tap-oracle-fusion
    > pip install -e .
    ```
2. Dependent libraries. The following dependent libraries were installed.
    ```bash
    > pip install singer-python
    > pip install target-stitch
    > pip install target-json

    ```
    - [singer-tools](https://github.com/singer-io/singer-tools)
    - [target-stitch](https://github.com/singer-io/target-stitch)

3. Create your tap's `config.json` file.  The tap config file for this tap should include these entries:
   - `start_date` - the default value to use if no bookmark exists for an endpoint (rfc3339 date string)
   - `user_agent` (string, optional): Process and email for API logging purposes. Example: `tap-oracle-fusion <api_user_email@your_company.com>`
   - `request_timeout` (integer, `300`): Max time for which request should wait to get a response. Default request_timeout is 300 seconds.

    ```json
    {
        "start_date": "2019-01-01T00:00:00Z",
        "user_agent": "tap-oracle-fusion <api_user_email@your_company.com>",
        "request_timeout": 300
    }```

    Optionally, also create a `state.json` file. `currently_syncing` is an optional attribute used for identifying the last object to be synced in case the job is interrupted mid-stream. The next run would begin where the last job left off.

    ```json
    {
        "currently_syncing": "engage",
        "bookmarks": {
            "export": "2019-09-27T22:34:39.000000Z",
            "funnels": "2019-09-28T15:30:26.000000Z",
            "revenue": "2019-09-28T18:23:53Z"
        }
    }
    ```

4. Run the Tap in Discovery Mode
    This creates a catalog.json for selecting objects/fields to integrate:
    ```bash
    tap-oracle-fusion --config config.json --discover > catalog.json
    ```
   See the Singer docs on discovery mode
   [here](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#discovery-mode).

5. Run the Tap in Sync Mode (with catalog) and [write out to state file](https://github.com/singer-io/getting-started/blob/master/docs/RUNNING_AND_DEVELOPING.md#running-a-singer-tap-with-a-singer-target)

    For Sync mode:
    ```bash
    > tap-oracle-fusion --config tap_config.json --catalog catalog.json > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    To load to json files to verify outputs:
    ```bash
    > tap-oracle-fusion --config tap_config.json --catalog catalog.json | target-json > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    To pseudo-load to [Stitch Import API](https://github.com/singer-io/target-stitch) with dry run:
    ```bash
    > tap-oracle-fusion --config tap_config.json --catalog catalog.json | target-stitch --config target_config.json --dry-run > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```

6. Test the Tap
    While developing the Oracle-fusion tap, the following utilities were run in accordance with Singer.io best practices:
    Pylint to improve [code quality](https://github.com/singer-io/getting-started/blob/master/docs/BEST_PRACTICES.md#code-quality):
    ```bash
    > pylint tap-oracle-fusion -d missing-docstring -d logging-format-interpolation -d too-many-locals -d too-many-arguments
    ```
    Pylint test resulted in the following score:
    ```bash
    Your code has been rated at 9.67/10
    ```

    To [check the tap](https://github.com/singer-io/singer-tools#singer-check-tap) and verify working:
    ```bash
    > tap-oracle-fusion --config tap_config.json --catalog catalog.json | singer-check-tap > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```

    #### Unit Tests

    Unit tests may be run with the following.

    ```
    python -m pytest --verbose
    ```

    Note, you may need to install test dependencies.

    ```
    pip install -e .'[dev]'
    ```
---

Copyright &copy; 2019 Stitch
