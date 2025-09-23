import argparse
from pathlib import Path

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>JavaScript Test</title>
</head>
<body>
  <h1>Testing JavaScript...</h1>
  <script>
    try {
      document.body.style.backgroundColor = 'orange';
      console.log('JavaScript is executing.');
    } catch (e) {
      document.body.innerHTML = `<h1>Error</h1><pre>${e.stack}</pre>`;
    }
  </script>
</body>
</html>
"""


def generate_test_file(run_dir: Path):
    output_path = run_dir / "chart.html"
    output_path.write_text(HTML_TEMPLATE)
    print(f"JavaScript test file saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a JS test file.")
    parser.add_argument(
        "run_directory",
        type=str,
        nargs="?",
        default="/Users/jbaird/Documents/personal/trading-platform/runs/researcher/run_20250920_043252_utc",
        help="Path to the run directory.",
    )
    args = parser.parse_args()
    generate_test_file(Path(args.run_directory))
