#!/usr/bin/env python3
"""Fix CLI test mocks to return proper dict format with compiled_strategy."""
import re
from pathlib import Path

# Files to fix
files = [
    "tests/cli/test_cli_100_percent_coverage.py",
    "tests/cli/test_cli_comprehensive.py",
    "tests/cli/test_cli_final_100.py",
]

for file_path in files:
    path = Path(file_path)
    if not path.exists():
        print(f"Skipping {file_path} - does not exist")
        continue

    content = path.read_text()
    original = content

    # Need to add pd import if not present
    if "import pandas as pd" not in content and "from pandas import" not in content:
        # Add after the last import
        import_lines = []
        other_lines = []
        in_imports = True
        for line in content.split('\n'):
            if in_imports and (line.startswith('import ') or line.startswith('from ') or line.strip() == '' or line.startswith('#')):
                import_lines.append(line)
            else:
                in_imports = False
                other_lines.append(line)

        # Insert pd import before first non-import line
        if import_lines:
            import_lines.append("import pandas as pd")
            content = '\n'.join(import_lines + other_lines)

    # Replace compiled_strategy: None with compiled_strategy: mock_strat
    # And ensure mock_strat has _feature_df attribute
    content = re.sub(
        r'(mock_strat = MagicMock\(\)\s+)(mock_compile\.return_value = mock_strat)',
        r'\1mock_strat._feature_df = pd.DataFrame()\n            \2',
        content,
        flags=re.MULTILINE
    )

    # Replace compiled_strategy: None with compiled_strategy: mock_strat
    content = re.sub(
        r'"compiled_strategy"\s*:\s*None',
        '"compiled_strategy": mock_strat',
        content
    )

    # Replace feature_enriched_df: None with feature_enriched_df: pd.DataFrame()
    content = re.sub(
        r'"feature_enriched_df"\s*:\s*df',
        '"feature_enriched_df": pd.DataFrame()',
        content
    )

    content = re.sub(
        r'"feature_enriched_df"\s*:\s*None',
        '"feature_enriched_df": pd.DataFrame()',
        content
    )

    if content != original:
        path.write_text(content)
        print(f"Fixed {file_path}")
    else:
        print(f"No changes needed in {file_path}")

print("\nDone!")
