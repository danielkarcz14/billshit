# Development

Python 3.11+; dependencies are declared in `pyproject.toml` and locked in `uv.lock`.
Run with `uv run billshit` from the checkout. uv installs the package in editable mode; templates and data remain in the checkout.

## Modules

- `cli.py`: argparse and exit codes.
- `app.py`: workflow and operation order.
- `config.py`: project paths, first-run setup, configuration validation.
- `period.py`: invoice numbers, issue dates and due dates.
- `invoices.py`: invoice documents, rates, quantities and expenses.
- `toggl.py`: HTTP client and aggregation of time entries.
- `storage.py`: TOML parsing, serialization and atomic writes.
- `pdf.py`: Typst PDF compilation.
- `errors.py`: errors displayed without a traceback.

## Tests

Run `uv run python -m unittest discover -v` from the project root.
