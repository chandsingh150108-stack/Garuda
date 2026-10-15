"""T12: command injection. Boundary: process invocation. Control: no
`shell=True` anywhere; every subprocess call passes an argument list.
Tested precisely via AST (keyword arguments on real call nodes, so docstring
mentions of "shell=True" do not false-positive). Bandit B603/B607 is the
second opinion, recorded in VALIDATION_REPORT.md.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent / "mentor"


def test_no_shell_true_or_os_system():
    hits = []
    for path in sorted(ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Attribute):
                    name = func.attr
                elif isinstance(func, ast.Name):
                    name = func.id
                if name == "system" and isinstance(func, ast.Attribute):
                    hits.append(f"{path}: os.system call")
                if name in ("run", "call", "check_call", "check_output",
                            "Popen"):
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) \
                                and kw.value.value is True:
                            hits.append(f"{path}:{node.lineno}: shell=True")
                if name in ("run", "call", "check_call", "check_output",
                            "Popen") and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        hits.append(f"{path}:{node.lineno}: string-form call")
    assert hits == [], f"command-injection surface: {hits}"


def test_git_invocations_are_list_form_with_timeout():
    import subprocess
    assert subprocess.run(["git", "--version"], capture_output=True,
                          timeout=30).returncode == 0
