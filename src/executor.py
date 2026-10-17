import ast
import os
import subprocess
import sys
import tempfile
from typing import Tuple, Optional

# Security Policy: Disallow process-spawning, raw OS commands, and networking libraries
BANNED_ROOT_MODULES = {
    "socket", "urllib", "requests", "http",
    "subprocess", "shutil", "pty",
    "multiprocessing", "threading"
}

BANNED_CALLS = {"system", "popen", "exec", "eval"}


def validate_ast_security(code: str) -> Tuple[bool, Optional[str]]:
    """
    Parses code into an AST and verifies syntax validity, import safety, and risky call safety.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError on line {e.lineno}: {e.msg}"

    for node in ast.walk(tree):
        # 1. Catch `import xyz`
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module in BANNED_ROOT_MODULES:
                    return False, f"Security Violation: Import of '{alias.name}' is prohibited."

        # 2. Catch `from xyz import abc`
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module in BANNED_ROOT_MODULES:
                    return False, f"Security Violation: Import from '{node.module}' is prohibited."
                if root_module == "os" and any(alias.name in BANNED_CALLS for alias in node.names):
                    return False, f"Security Violation: Importing unsafe OS call is prohibited."

        # 3. Catch direct calls like `os.system(...)` or `eval(...)`
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_CALLS:
                return False, f"Security Violation: Call to '{node.func.attr}()' is prohibited."
            elif isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
                return False, f"Security Violation: Call to '{node.func.id}()' is prohibited."

    return True, None


def execute_pycode(code: str, timeout_seconds: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Executes Python code in an isolated subprocess with syntax validation,
    sanitized environment, disposable working directory, and timeout limits.
    """
    # 1. AST Validation & Security Audit (replaces redundant ast.parse)
    is_safe, security_error = validate_ast_security(code)
    if not is_safe:
        return False, security_error

    # 2. Sanitized Environment (prevents API key and secret leakage)
    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Required on Windows
        "PYTHONPATH": "",  # Disallows importing local repository modules
    }

    # 3. Disposable Sandbox Execution
    with tempfile.TemporaryDirectory() as sandbox_dir:
        temp_path = os.path.join(sandbox_dir, "run_target.py")

        with open(temp_path, "w", encoding="utf-8") as temp_file:
            temp_file.write(code)

        try:
            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=sandbox_dir,  # Confines any generated files to the temp directory
                env=clean_env
            )

            if result.returncode == 0:
                return True, None
            else:
                stderr_output = result.stderr.strip()
                # Truncate verbose errors to avoid token inflation
                if len(stderr_output) > 2000:
                    stderr_output = stderr_output[:2000] + "\n... [Traceback Truncated]"
                return False, stderr_output

        except subprocess.TimeoutExpired:
            return False, f"Execution timed out after {timeout_seconds} seconds (possible infinite loop)."
        except Exception as e:
            return False, f"Sandbox runtime error: {str(e)}"


if __name__ == "__main__":
    print("1. Testing valid code:")
    ok, err = execute_pycode("def add(a, b): return a + b\nassert add(2, 3) == 5")
    print(f"Result: success={ok}, err={err}")

    print("\n2. Testing failing assert:")
    ok, err = execute_pycode("assert 1 == 2")
    print(f"Result: success={ok}, err={err}")

    print("\n3. Testing banned import:")
    ok, err = execute_pycode("import socket\ns = socket.socket()")
    print(f"Result: success={ok}, err={err}")

    print("\n4. Testing os.system attempt:")
    ok, err = execute_pycode("import os\nos.system('dir')")
    print(f"Result: success={ok}, err={err}")