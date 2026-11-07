"""Read-only fail-closed readiness check for the live signed root broker.

This checker does not activate, restart or reconfigure services. A passing
staging suite is intentionally NOT sufficient for production approval.
"""
import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    broker = ast.parse((ROOT / "agency/systemd_broker.py").read_text())
    signed = ast.parse((ROOT / "agency/supervised_broker.py").read_text())
    def function(tree, name):
        matches = [node for node in tree.body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == name]
        if len(matches) != 1:
            raise RuntimeError("Missing or ambiguous function: " + name)
        return matches[0]
    execute = function(broker, "execute_signed_grant")
    listener = function(broker, "handle_signed_connection")
    serve = function(signed, "serve_forever")
    def calls(node, name):
        return any(isinstance(child, ast.Call)
                   and isinstance(child.func, ast.Name)
                   and child.func.id == name for child in ast.walk(node))
    legacy = calls(listener, "execute_signed_grant") and calls(execute, "executor")
    print("LEGACY_UNFENCED_SIGNED_PATH=" + ("PRESENT" if legacy else "NOT_DETECTED"))
    print("ROOT_BROKER_LISTENER=" + ("PRESENT" if calls(serve, "handle_signed_connection") else "NOT_DETECTED"))
    # Never infer readiness from a missing AST pattern: production requires
    # separate crash/rollback acceptance and explicit operator authorization.
    print("PRODUCTION_FENCED_CUTOVER_APPROVED=NO")
    if legacy:
        raise PermissionError("Active signed broker still admits an unfenced executor")
    raise PermissionError("Production cutover requires independent acceptance")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    check()


if __name__ == "__main__":
    main()
