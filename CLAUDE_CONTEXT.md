# Claude Context for Trading Platform

## Quick Start for New Conversations

When starting new conversations with Claude, reference this context:

1. **Review [docs/project_requirements.md](docs/project_requirements.md)** - Core standards and architecture
2. **Check current branch**: Run `git status` and `git log --oneline -5`
3. **Verify test baseline**: All tests should be passing before starting work

## Core Project Standards

- **Python 3.13+** with `mypy --strict` typing
- **100% test coverage** with pytest
- **Code style**: Black + Ruff
- **Validation**: Pydantic models
- **Architecture**: Event-driven, fail-fast validation, no silent failures

## Key Principles

- **Separation of Concerns**: Strategy logic ≠ REM risk exits ≠ RMM regime context
- **Testing Layers**: L1 (manual verification) → L2 (core) → L3 (integration) → L4 (realistic)
- **Immutable Data**: Defensive programming patterns
- **Golden Master**: Regression testing with snapshots

## Common Workflows

- **Before coding**: Create todo list for multi-step tasks
- **Test-first**: Write/update tests before implementation
- **Type safety**: Ensure mypy passes on all changes
- **Documentation**: Update schemas and docs when changing data structures