#!/usr/bin/env python3
"""Runner & Verification Script for VinAI K4 Day 26: MCP & Function Calling.

Executes and verifies all 4 modules:
1. 01-function-calling: Pure Function Calling with Google Gemini SDK
2. 02-mcp-basics: MCP Server & Client via stdio
3. 03-production:
   - 3a: Auth Server & Client (Bearer Token via Streamable HTTP)
   - 3b: Tool Registry & Discovery
   - 3c: Versioning & Backward Compatibility
4. 04-lab: Weather Agent with Google ADK + Remote FastMCP Server
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = ROOT_DIR / ".venv" / "bin" / "python"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)


def print_banner(title: str) -> None:
    line = "=" * 65
    print(f"\n{line}\n  {title}\n{line}\n")


def run_command(cmd: list[str], cwd: Path, timeout: float = 60) -> tuple[int, str]:
    """Run a command in subprocess and return (exit_code, output)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        return -1, f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as e:
        return -1, f"Error running command: {e}"


def test_01_function_calling() -> bool:
    print_banner("1. Testing 01-function-calling (Gemini SDK)")
    cwd = ROOT_DIR / "01-function-calling"
    code, out = run_command([str(PYTHON_EXE), "weather_function_calling.py"], cwd=cwd, timeout=30)
    print(out)
    if code == 0 and "get_weather" in out:
        print("✅ 01-function-calling: PASSED")
        return True
    print(f"❌ 01-function-calling: FAILED (exit code {code})")
    return False


def test_02_mcp_basics() -> bool:
    print_banner("2. Testing 02-mcp-basics (MCP stdio Server + Client)")
    cwd = ROOT_DIR / "02-mcp-basics"
    code, out = run_command([str(PYTHON_EXE), "weather_client.py"], cwd=cwd, timeout=30)
    print(out)
    if code == 0 and "get_weather" in out and "Hanoi" in out:
        print("✅ 02-mcp-basics: PASSED")
        return True
    print(f"❌ 02-mcp-basics: FAILED (exit code {code})")
    return False


def test_03_production() -> bool:
    print_banner("3. Testing 03-production (Auth, Registry, Versioning)")
    cwd = ROOT_DIR / "03-production"
    all_ok = True

    # 3a. Auth
    print("--- [3a] Auth Server & Client ---")
    server_proc = subprocess.Popen(
        [str(PYTHON_EXE), "auth_server.py"],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2.5)
    try:
        code_c, out_c = run_command([str(PYTHON_EXE), "auth_client.py"], cwd=cwd, timeout=20)
        print(out_c)
        if code_c == 0 and "Tools (có auth)" in out_c:
            print("✅ 3a Auth: PASSED")
        else:
            print(f"❌ 3a Auth: FAILED (exit code {code_c})")
            all_ok = False
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()

    # 3b. Registry
    print("\n--- [3b] Tool Registry & Discovery ---")
    code_r, out_r = run_command([str(PYTHON_EXE), "registry_client.py"], cwd=cwd, timeout=20)
    print(out_r)
    if code_r == 0 and "Best match" in out_r:
        print("✅ 3b Registry: PASSED")
    else:
        print(f"❌ 3b Registry: FAILED (exit code {code_r})")
        all_ok = False

    # 3c. Versioning
    print("\n--- [3c] Versioning & Backward Compatibility ---")
    code_v, out_v = run_command([str(PYTHON_EXE), "versioned_client.py"], cwd=cwd, timeout=20)
    print(out_v)
    if code_v == 0 and "get_weather_v2" in out_v:
        print("✅ 3c Versioning: PASSED")
    else:
        print(f"❌ 3c Versioning: FAILED (exit code {code_v})")
        all_ok = False

    return all_ok


def test_04_lab() -> bool:
    print_banner("4. Testing 04-lab (Google ADK Weather Agent + FastMCP)")
    server_dir = ROOT_DIR / "04-lab" / "mcp-server"
    client_dir = ROOT_DIR / "04-lab" / "mcp-client"

    # Start weather server daemon on port 8085
    server_proc = subprocess.Popen(
        ["uv", "run", "python", "weather.py"],
        cwd=str(server_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2.5)

    all_ok = True
    try:
        # Run verify_setup.py
        print("--- [4a] Verifying Lab Setup ---")
        code_v, out_v = run_command(["uv", "run", "python", "verify_setup.py"], cwd=client_dir, timeout=25)
        print(out_v)
        if code_v != 0 or "All checks passed!" not in out_v:
            print("❌ 4a verify_setup: FAILED")
            all_ok = False
        else:
            print("✅ 4a verify_setup: PASSED")

        # Run ADK agent query
        print("\n--- [4b] Running ADK Weather Agent Query ---")
        code_q, out_q = run_command(
            ["uv", "run", "adk", "run", "weather_agent", "What is the current weather in Hanoi?"],
            cwd=client_dir,
            timeout=30,
        )
        print(out_q)
        if code_q == 0 and "[weather_agent]" in out_q and "Hanoi" in out_q:
            print("✅ 4b ADK Agent Query: PASSED")
        else:
            print(f"❌ 4b ADK Agent Query: FAILED (exit code {code_q})")
            all_ok = False

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()

    return all_ok


def main() -> int:
    print_banner("K4-Day26: MCP & Function Calling Comprehensive Test Runner")
    results = {
        "01-function-calling": test_01_function_calling(),
        "02-mcp-basics": test_02_mcp_basics(),
        "03-production": test_03_production(),
        "04-lab": test_04_lab(),
    }

    print_banner("SUMMARY OF TEST RESULTS")
    all_passed = True
    for module, passed in results.items():
        status = "PASSED ✅" if passed else "FAILED ❌"
        if not passed:
            all_passed = False
        print(f"  • {module:<22}: {status}")

    print("\n" + "=" * 65)
    if all_passed:
        print("  🎉 ALL MODULES PASSED SUCCESSFULLY!")
        print("=" * 65)
        return 0
    else:
        print("  ⚠️  SOME MODULES FAILED. Please check logs above.")
        print("=" * 65)
        return 1


if __name__ == "__main__":
    sys.exit(main())
