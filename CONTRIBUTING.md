# Contributing to NetBox Unified Deployment

First off, thank you for considering contributing to this project!

## Development Setup

1. Clone the repository.
2. Ensure you have Python 3.9+ installed.
3. It is recommended to use `venv` and install development dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
4. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Pull Request Process

1. Create a feature branch from `main`.
2. Ensure your code passes all linting (Ruff), type checking (Mypy), and tests.
   ```bash
   pytest
   ruff check .
   mypy automation/
   ```
3. Submit a Pull Request targeting the `main` branch.
4. The CI pipeline will automatically run checks. Ensure all CI jobs pass.

## Coding Standards

- We use **Ruff** for linting and formatting.
- We require **Mypy** static typing for all new Python code.
- Write unit tests for new features. We aim for 100% test pass rate and high coverage.
