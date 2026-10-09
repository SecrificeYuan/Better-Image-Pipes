"""Enforce the approved C++ export scope against the public baseline."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXISTING = {
    "backend/app/api/routes.py", "frontend/src/features/code/CodePanel.tsx",
    "frontend/src/hooks/useExecutionSocket.ts", "frontend/src/store/graphStore.ts",
    "frontend/src/i18n/en.json", "frontend/src/i18n/zh-CN.json",
    "frontend/package.json", "frontend/package-lock.json", "scripts/verify-localization.mjs",
    "desktop/package.json", "README.md",
}
ADDED = {
    "backend/tests/test_codegen_cpp.py", "backend/tests/test_codegen_cpp_native.py",
    "backend/tests/helpers/cpp_codegen_cases.py", "frontend/playwright.config.ts",
    "frontend/e2e/code-export.spec.ts", ".github/workflows/cpp-export.yml",
    "docs/cpp-export.md", "docs/cpp-export-plan.md", "docs/baseline-manifest.json",
    "scripts/verify-cpp-export-scope.py",
} | {f"backend/app/services/cpp_codegen/{name}.py" for name in (
    "__init__", "compiler", "common", "io", "color", "filters", "analysis", "geometry",
    "math", "morphology", "clustering", "structure",
)}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).splitlines()


if __name__ == "__main__":
    original = set(git("ls-tree", "-r", "--name-only", "baseline-20261010"))
    changed = set(git("diff", "--name-only", "baseline-20261010"))
    changed.update(git("ls-files", "--others", "--exclude-standard"))
    violations = sorted(p for p in changed if p not in (EXISTING if p in original else ADDED))
    if violations:
        raise SystemExit("Changes outside frozen scope:\n" + "\n".join(violations))
    print(f"Frozen scope verified: {len(changed)} files, baseline-20261010")
