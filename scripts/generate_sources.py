import sys

from scripts.generators.department_generator import DepartmentGenerator
from scripts.generators.fx_generator import FXRateGenerator
from scripts.generators.region_generator import RegionGenerator
from scripts.generators.product_generator import ProductGenerator
from scripts.generators.product_price_book_generator import ProductPriceBookGenerator
from scripts.generators.employee_generator import EmployeeGenerator
from scripts.generators.customer_generator import CustomerGenerator
from scripts.generators.crm_generator import CRMGenerator
from scripts.generators.billing_subscriptions_generator import SubscriptionGenerator
from scripts.generators.subscription_events_generator import SubscriptionEventsGenerator
from scripts.generators.billing_invoices_generator import BillingInvoicesGenerator
from scripts.generators.billing_payments_generator import BillingPaymentsGenerator
from scripts.generators.revenue_recognition_generator import RevenueRecognitionGenerator
from scripts.generators.chart_of_accounts_generator import ChartOfAccountsGenerator
from scripts.generators.erp_gl_journal_lines_generator import ERPGLJournalLinesGenerator
from scripts.generators.vendors_generator import VendorsGenerator
from scripts.generators.vendor_invoices_generator import VendorInvoicesGenerator
from scripts.generators.vendor_payments_generator import VendorPaymentsGenerator
from scripts.generators.ap_ageing_snapshot_generator import APAgeingSnapshotGenerator
from scripts.generators.trial_balance_generator import TrialBalanceGenerator
from scripts.generators.financial_statement_extract_generator import FinancialStatementExtractGenerator
from scripts.generators.financial_statement_control_summary_generator import FinancialStatementControlSummaryGenerator
from scripts.generators.control_findings_register_generator import ControlFindingsRegisterGenerator
from scripts.generators.workforce_cost_generator import WorkforceCostGenerator
from scripts.generators.budget_generator import BudgetGenerator
from scripts.utils.logger import get_logger


logger = get_logger("PipelineOrchestrator", "generation_execution.log")


def main() -> None:
    logger.info("=" * 72)
    logger.info("STARTING PROJECT ATLAS SYNTHETIC SOURCE GENERATION")
    logger.info("=" * 72)

    try:
        logger.info("Phase 3A.1: Generating FX rates")
        fx_generator = FXRateGenerator()
        fx_rates = fx_generator.generate()
        fx_generator.save(fx_rates)
        logger.info("FX generation complete: %s rows", len(fx_rates))

        logger.info("Phase 3A.2: Generating product catalogue")
        product_generator = ProductGenerator()
        products = product_generator.generate()
        product_generator.save(products)
        logger.info("Product generation complete: %s rows", len(products))

        logger.info("Phase 3A.2b: Generating product price book")
        price_book_generator = ProductPriceBookGenerator()
        price_book = price_book_generator.generate()
        price_book_generator.save(price_book)
        logger.info("Product price book generation complete: %s rows", len(price_book))

        logger.info("Phase 3A.3: Generating department catalogue")
        department_generator = DepartmentGenerator()
        departments = department_generator.generate()
        department_generator.save(departments)
        logger.info("Department generation complete: %s rows", len(departments))

        logger.info("Phase 3A.2: Generating region catalogue")
        region_generator = RegionGenerator()
        regions = region_generator.generate()
        region_generator.save(regions)
        logger.info("Region generation complete: %s rows", len(regions))

        logger.info("Phase 3B.1: Generating billing customer master")
        customer_generator = CustomerGenerator()
        customers = customer_generator.generate()
        customer_generator.save(customers)
        logger.info("Customer generation complete: %s rows", len(customers))

        logger.info("Phase 3B.2: Generating CRM account export")
        crm_generator = CRMGenerator()
        crm_accounts = crm_generator.generate()
        crm_generator.save(crm_accounts)
        logger.info("CRM generation complete: %s rows", len(crm_accounts))

        logger.info("Phase 3C.1: Generating HRIS employee master and headcount snapshot")
        employee_generator = EmployeeGenerator()
        employees, headcount_snapshot = employee_generator.generate()
        employee_generator.save(employees, headcount_snapshot)
        logger.info(
           "HRIS generation complete: %s employee rows, %s snapshot rows",
           len(employees),
           len(headcount_snapshot),
        )

        logger.info("Phase 3D: Generating billing subscription master")
        subscription_generator = SubscriptionGenerator()
        subscriptions = subscription_generator.generate()
        subscription_generator.save(subscriptions)
        logger.info("Subscription generation complete: %s rows", len(subscriptions))

        logger.info("Phase 3D.2: Generating billing subscription events")
        subscription_events_generator = SubscriptionEventsGenerator()
        subscription_events = subscription_events_generator.generate()
        subscription_events_generator.save(subscription_events)
        logger.info(
            "Subscription events generation complete: %s rows",
            len(subscription_events),
        )

        logger.info("Phase 3E: Generating billing invoices and invoice lines")
        billing_invoices_generator = BillingInvoicesGenerator()
        invoice_headers, invoice_lines = billing_invoices_generator.generate()
        billing_invoices_generator.save(invoice_headers, invoice_lines)
        logger.info(
            "Billing invoice generation complete: %s headers, %s lines",
            len(invoice_headers),
            len(invoice_lines),
        )

        logger.info("Phase 3F: Generating payments, cash receipts and AR ageing")
        billing_payments_generator = BillingPaymentsGenerator()
        payments, payment_allocations, ar_ageing_snapshot = (
            billing_payments_generator.generate()
        )
        billing_payments_generator.save(
            payments_df=payments,
            allocations_df=payment_allocations,
            ageing_df=ar_ageing_snapshot,
        )
        logger.info(
            "Payments and AR ageing generation complete: %s payments, %s allocations, %s ageing rows",
            len(payments),
            len(payment_allocations),
            len(ar_ageing_snapshot),
        )
        logger.info("Phase 3G: Generating revenue recognition and deferred revenue")

        revenue_recognition_generator = RevenueRecognitionGenerator()
        revenue_recognition_schedule, deferred_revenue_rollforward = (
            revenue_recognition_generator.generate()
        )

        revenue_recognition_generator.save(
            schedule_df=revenue_recognition_schedule,
            rollforward_df=deferred_revenue_rollforward,
        )

        logger.info(
            "Revenue recognition generation complete: %s schedule rows, %s deferred revenue roll-forward rows",
            f"{len(revenue_recognition_schedule):,}",
            f"{len(deferred_revenue_rollforward):,}",
        )

        logger.info("Phase 3H.1: Generating chart of accounts")

        chart_of_accounts_generator = ChartOfAccountsGenerator()
        chart_of_accounts = chart_of_accounts_generator.generate()
        chart_of_accounts_generator.save(chart_of_accounts)

        logger.info(
            "Chart of Accounts generation complete: %s accounts",
            f"{len(chart_of_accounts):,}",
        )

        logger.info("Phase 3I.1: Generating procurement vendor master")

        vendors_generator = VendorsGenerator()
        vendors = vendors_generator.generate()
        vendors_generator.save(vendors)

        logger.info(
            "Vendor master generation complete: %s vendors",
            f"{len(vendors):,}",
        )

        logger.info("Phase 3I.2: Generating vendor invoices and invoice lines")

        vendor_invoices_generator = VendorInvoicesGenerator()
        vendor_invoice_headers, vendor_invoice_lines = vendor_invoices_generator.generate()
        vendor_invoices_generator.save(
            headers_df=vendor_invoice_headers,
            lines_df=vendor_invoice_lines,
        )

        logger.info(
            "Vendor invoice generation complete: %s headers, %s lines",
            f"{len(vendor_invoice_headers):,}",
            f"{len(vendor_invoice_lines):,}",
        )

        logger.info("Phase 3I.3: Generating vendor payments and AP settlement")

        vendor_payments_generator = VendorPaymentsGenerator()
        vendor_payments = vendor_payments_generator.generate()
        vendor_payments_generator.save(vendor_payments)

        logger.info(
            "Vendor payments generation complete: %s payments",
            f"{len(vendor_payments):,}",
        )

        logger.info("Phase 3I.4: Generating AP ageing snapshot")

        ap_ageing_snapshot_generator = APAgeingSnapshotGenerator()
        ap_ageing_snapshot = ap_ageing_snapshot_generator.generate()
        ap_ageing_snapshot_generator.save(ap_ageing_snapshot)

        logger.info(
            "AP ageing snapshot generation complete: %s rows",
            f"{len(ap_ageing_snapshot):,}",
        )

        logger.info("Phase 3I.5: Generating ERP GL journal lines including Q2C and P2P")

        erp_gl_journal_lines_generator = ERPGLJournalLinesGenerator()
        erp_gl_journal_lines = erp_gl_journal_lines_generator.generate()
        erp_gl_journal_lines_generator.save(erp_gl_journal_lines)

        logger.info(
            "ERP GL journal lines generation complete: %s journal lines",
            f"{len(erp_gl_journal_lines):,}",
        )

        logger.info("Phase 3J.1: Generating Trial Balance extract")

        trial_balance_generator = TrialBalanceGenerator()
        trial_balance = trial_balance_generator.generate()
        trial_balance_generator.save(trial_balance)

        logger.info(
            "Trial Balance generation complete: %s rows",
            f"{len(trial_balance):,}",
        )

        logger.info("Phase 3J.2: Generating Financial Statement extract")

        financial_statement_generator = FinancialStatementExtractGenerator()
        financial_statement_extract = financial_statement_generator.generate()
        financial_statement_generator.save(financial_statement_extract)

        logger.info(
            "Financial Statement extract generation complete: %s rows",
            f"{len(financial_statement_extract):,}",
        )

        logger.info("Phase 3J.3: Generating Financial Statement control summary")

        financial_statement_control_generator = FinancialStatementControlSummaryGenerator()
        financial_statement_controls = financial_statement_control_generator.generate()
        financial_statement_control_generator.save(financial_statement_controls)

        logger.info(
            "Financial Statement control summary generation complete: %s rows",
            f"{len(financial_statement_controls):,}",
        )

        logger.info("Phase 3J.4: Generating Control Findings Register")

        control_findings_register_generator = ControlFindingsRegisterGenerator()
        control_findings_register = control_findings_register_generator.generate()
        control_findings_register_generator.save(control_findings_register)

        logger.info(
            "Control Findings Register generation complete: %s findings",
            f"{len(control_findings_register):,}",
        )

        logger.info("Phase 3K.1: Generating workforce cost source extracts")

        workforce_cost_generator = WorkforceCostGenerator()
        employee_compensation, payroll_expense_lines, headcount_plan = (
            workforce_cost_generator.generate()
        )
        workforce_cost_generator.save(
            compensation_df=employee_compensation,
            payroll_df=payroll_expense_lines,
            headcount_plan_df=headcount_plan,
        )

        logger.info(
            "Workforce cost generation complete: %s compensation rows, %s payroll rows, %s headcount plan rows",
            f"{len(employee_compensation):,}",
            f"{len(payroll_expense_lines):,}",
            f"{len(headcount_plan):,}",
        )

        logger.info("Phase 3L.1: Generating Budget / Annual Operating Plan source extracts")

        budget_generator = BudgetGenerator()
        budget_versions, budget_lines = budget_generator.generate()
        budget_generator.save(budget_versions, budget_lines)

        logger.info(
            "Budget generation complete: %s versions, %s lines",
            f"{len(budget_versions):,}",
            f"{len(budget_lines):,}",
        )

        logger.info("=" * 72)
        logger.info("SOURCE GENERATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 72)

    except Exception as error:
        logger.critical(
            "Source generation failed: %s",
            error,
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()