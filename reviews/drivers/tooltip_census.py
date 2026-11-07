"""Who shows or hides chart tooltips? One line per call site, grouped by file and function."""
import ast, sys
from pathlib import Path
ROOT = Path(sys.argv[1]) / "src/manic/ui"
for path in sorted(ROOT.glob("*.py")):
    tree = ast.parse(path.read_text())
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr in ("showText", "hideText", "show_identity_tooltip", "refresh")]
        kinds = sorted({c.func.attr for c in calls})
        if kinds:
            print(f"{path.name}:{fn.lineno} {fn.name}: {', '.join(kinds)}")
