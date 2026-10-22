# billshit

## Requirements

- uv
- Typst 

## Configuration

The first run creates configuration files from the templates:

```sh
uv run billshit
```

- `data/config.toml`: supplier details, bank account, PDF filename prefix.
- `data/nova.toml`: hourly rates, including the foreign work surcharge.
- `~/.config/toggl/token`: Toggl API token.


## Usage

```sh
uv run billshit 10-2026
uv run billshit --expenses 1193.26 10-2026
uv run billshit --pdf 10-2026           # saved data, no Toggl import
uv run billshit --help
```

Repeated runs update hours and preserve rates, dates and manual invoice edits.

- Output: `data/faktury/MM-YYYY/`.

## Development

```sh
uv run python -m unittest discover -v
```

Module overview: [docs/development.md](docs/development.md).
