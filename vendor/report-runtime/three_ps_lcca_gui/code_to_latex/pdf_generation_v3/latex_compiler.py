from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class LatexCompiler:
    name: str
    executable: str


def discover_latex_compiler(
    which: Callable[[str], str | None] = shutil.which,
) -> LatexCompiler | None:
    """Prefer Tectonic, then fall back to a system pdflatex executable."""
    tectonic = which("tectonic")
    if tectonic:
        return LatexCompiler("tectonic", tectonic)

    pdflatex = which("pdflatex")
    if pdflatex:
        return LatexCompiler("pdflatex", pdflatex)

    return None


def build_compiler_command(
    compiler: LatexCompiler,
    tex_path: Path,
    work_dir: Path,
    *extra_args: str,
) -> list[str]:
    if compiler.name == "tectonic":
        return [
            compiler.executable,
            "--keep-logs",
            "--outdir",
            str(work_dir),
            str(tex_path),
        ]

    if compiler.name == "pdflatex":
        return [
            compiler.executable,
            "-interaction=nonstopmode",
            *extra_args,
            tex_path.name,
        ]

    raise ValueError(f"Unsupported LaTeX compiler: {compiler.name}")


def run_compiler(
    compiler: LatexCompiler,
    tex_path: Path,
    work_dir: Path,
    *extra_args: str,
    runner=None,
):
    command = build_compiler_command(compiler, tex_path, work_dir, *extra_args)
    run = runner or subprocess.run
    return run(
        command,
        cwd=work_dir,
        capture_output=True,
        text=True,
    )


def tectonic_network_hint(output: str) -> str:
    """Return an actionable hint for likely first-run resource download failures."""
    text = output.lower()
    network_markers = (
        "network",
        "failed to fetch",
        "failed to download",
        "failed to retrieve",
        "connection",
        "dns",
        "certificate",
        "timed out",
        "timeout",
        "http error",
        "ssl",
    )
    if any(marker in text for marker in network_markers):
        return (
            "\n\nTectonic downloads and caches LaTeX resources when the first "
            "report is generated. Connect to the internet and try again. "
            "After a successful report, the cached resources can be reused offline."
        )
    return ""


def compiler_version(compiler: LatexCompiler) -> str:
    try:
        result = subprocess.run(
            [compiler.executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return "version unavailable"

    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else "version unavailable"
