# Claude Code Instructions for Trading Platform Project

## Bash Command Execution

**CRITICAL: Never run bash commands directly with the Bash tool.**

Instead, follow this workflow:
1. Use the **Write** or **Edit** tool to update `workspace/run.sh` with your command
2. Execute the script using: `./workspace/run.sh`

**DO NOT** use `cat`, `echo`, or any bash command to edit `run.sh` - use the Write/Edit tools directly.

### Examples

❌ **WRONG:**
```bash
poetry run python script.py
bash -c "python script.py"
```

✅ **CORRECT:**
1. Edit `workspace/run.sh` with the Write/Edit tool to contain your command
2. Run: `./workspace/run.sh`

This ensures proper environment setup and consistency across all command executions in this project.
