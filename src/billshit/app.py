"""Application workflow; modules communicate through explicit inputs and results."""

from dataclasses import dataclass, field
from decimal import Decimal

from .config import Paths, TogglSettings, load_settings, prepare
from .errors import BillshitError
from .invoices import Invoice
from .pdf import Renderer
from .period import Period
from .storage import load_toml, save_toml
from .toggl import TogglClient, read_token


@dataclass(frozen=True)
class Options:
    period: Period = field(default_factory=Period.current)
    expenses: Decimal | None = None
    pdf: bool = False
    force: bool = False


def run(options: Options, paths: Paths, client_factory=None) -> int:
    sync = not options.pdf
    if prepare(paths, use_toggl=sync):
        print("Configuration files created. Before generating your first invoice:")
        print(f"  {paths.config} – enter your details, bank account and PDF filename prefix.")
        print(f"  {paths.template} – set hourly rates, including the foreign work surcharge.")
        print(f"  {paths.token} – save your Toggl API token.")
        print("Then run the same command again.")
        return 1

    settings, prefix = load_settings(paths)
    invoice_path = paths.invoice(options.period)
    output = paths.pdf(options.period, prefix)
    create = sync and not invoice_path.exists()
    renderer = Renderer(paths)
    renderer.check(output, options.force)

    if create:
        invoice = Invoice.create(load_toml(paths.template), options.period)
    else:
        invoice = Invoice(load_toml(invoice_path))
    invoice.validate()
    report = None
    if sync:
        rules = TogglSettings.from_config(settings)
        client = (client_factory or TogglClient)(read_token(paths.token))
        report = client.report(options.period, rules)
        invoice.apply_hours(report.hours, rules, load_toml(paths.template))
    if options.expenses is not None:
        invoice.set_expenses(options.expenses)
    invoice.validate()
    if sync or options.expenses is not None:
        save_toml(invoice_path, invoice.document)
    if create:
        print(f"Created {invoice_path}.")
    if report is not None:
        report.print_summary(options.period, rules)
    if options.expenses is not None:
        print(f"Expenses: {options.expenses} CZK")
    renderer.render(invoice_path, output, force=options.force)
    return 0
