import os
from pathlib import Path


here = Path(__file__).resolve()
git_exe = None

for parent in here.parents:
    candidate = parent / "git" / "cmd" / "git.exe"
    if candidate.exists():
        git_exe = candidate
        break

if git_exe:
    os.environ.setdefault("GIT_PYTHON_GIT_EXECUTABLE", str(git_exe))
    os.environ["PATH"] = f"{git_exe.parent}{os.pathsep}{os.environ.get('PATH', '')}"
