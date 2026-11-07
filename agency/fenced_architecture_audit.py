"""Read-only architecture audit of fenced execution boundaries.

Run against source checkout; never imports production application or changes services.
"""
import ast
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    "agency/systemd_jobs.py": ("run_systemd_job",),
    "agency/fenced_systemd_supervisor.py": ("supervised_fenced_unit", "run_fenced_systemd_unit"),
    "agency/fenced_unit_journal.py": ("register_before_launch", "recover_owned_units"),
    "agency/fenced_startup_gate.py": ("require_recovered",),
    "agency/trusted_lease_ipc.py": ("serve_fence_connection", "broker_fenced_job"),
}
DANGEROUS_CALLS = {"systemd-run", "subprocess.run", "subprocess.Popen", "os.system", "os.execv", "os.execve"}


def audit():
    failures = []
    for path, functions in CHECKS.items():
        source = (ROOT / path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=path)
        names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        missing = set(functions) - names
        if missing:
            failures.append(path + ": missing " + repr(sorted(missing)))
        else:
            print("AUDIT_MODULE_PRESENT=" + path, flush=True)
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".git", ".venv", "venv", "__pycache__"} for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError):
            failures.append(str(path.relative_to(ROOT)) + ": unparsable")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                name = node.func.value.id + "." + node.func.attr
            if name in DANGEROUS_CALLS:
                print("EXECUTION_CALLSITE=" + str(path.relative_to(ROOT)) +
                      ":" + str(node.lineno) + ":" + name, flush=True)
    if failures:
        raise RuntimeError("Source audit incomplete: " + "; ".join(failures))
    print("SOURCE_AUDIT_COMPLETED=PASS", flush=True)
    print("PRODUCTION_WIRING_VERIFIED=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    audit()


if __name__ == "__main__":
    main()
