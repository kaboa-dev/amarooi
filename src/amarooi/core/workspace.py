"""Workspace helpers for Amarooi specs, extracted contracts, and generated code."""

from __future__ import annotations

from pathlib import Path

TARGET_ALIASES: dict[str, str] = {
    "py": "python",
    "python": "python",
    "rs": "rust",
    "rust": "rust",
    "cpp": "c++",
    "c++": "c++",
    "java": "java",
    "ts": "typescript",
    "typescript": "typescript",
}

TARGET_EXTENSIONS: dict[str, str] = {
    "python": ".py",
    "rust": ".rs",
    "c++": ".cpp",
    "java": ".java",
    "typescript": ".ts",
}

TARGET_BADGE_STYLES: dict[str, str] = {
    "python": "black on yellow",
    "rust": "white on red",
    "c++": "white on blue",
    "java": "white on magenta",
    "typescript": "white on cyan",
}

TARGET_BADGE_LABELS: dict[str, str] = {
    "python": "PYTHON",
    "rust": "RUST",
    "c++": "C++",
    "java": "JAVA",
    "typescript": "TS",
}


def normalize_target(target: str | None) -> str:
    """Return the canonical target name for *target*."""
    if target is None:
        return "python"
    normalised = target.strip().lower()
    canonical = TARGET_ALIASES.get(normalised)
    if canonical is None:
        supported = ", ".join(sorted(TARGET_ALIASES))
        raise ValueError(f"Unsupported target {target!r}. Expected one of: {supported}.")
    return canonical


def target_extension(target: str) -> str:
    """Return the source-file extension for *target*."""
    return TARGET_EXTENSIONS[normalize_target(target)]


def target_badge(target: str) -> str:
    """Return Rich markup for a color-coded target badge."""
    canonical = normalize_target(target)
    style = TARGET_BADGE_STYLES[canonical]
    label = TARGET_BADGE_LABELS[canonical]
    return f"[bold {style}] {label} [/bold {style}]"


def _safe_component_name(component_name: str) -> str:
    return component_name.replace(" ", "_").lower()


def _spec_stem(path: str | Path) -> str:
    name = Path(path).name
    for suffix in (".amarooi.json", ".amarooi"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(path).stem


class WorkspaceManager:
    """Manage a directory of writable ``.amarooi`` specification files."""

    def __init__(self, workspace_dir: str | Path = "specs") -> None:
        self.workspace_dir: Path = Path(workspace_dir).resolve()

    def ensure_dir(self) -> None:
        """Create the workspace directory if needed."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def filepath(self, component_name: str) -> Path:
        """Return the canonical ``.amarooi`` path for *component_name*."""
        return self.workspace_dir / f"{_safe_component_name(component_name)}.amarooi"

    def write(self, component_name: str, content: str) -> Path:
        """Write *content* to the component's ``.amarooi`` file."""
        self.ensure_dir()
        path = self.filepath(component_name)
        path.write_text(content, encoding="utf-8")
        return path


class ProjectWorkspace:
    """Resolve isolated repo-local directories for generated Amarooi assets."""

    def __init__(self, root_dir: str | Path = ".") -> None:
        self.root_dir = Path(root_dir).resolve()

    @classmethod
    def from_path(cls, path: str | Path) -> "ProjectWorkspace":
        """Infer the workspace root for *path*."""
        resolved = Path(path).resolve()
        for parent in resolved.parents:
            if parent.name in {"specs", "extracted_specs", "src_generated"}:
                return cls(parent.parent)
        return cls(resolved.parent if resolved.suffix else resolved)

    @property
    def specs_dir(self) -> Path:
        return self.root_dir / "specs"

    @property
    def extracted_specs_dir(self) -> Path:
        return self.root_dir / "extracted_specs"

    @property
    def generated_root_dir(self) -> Path:
        return self.root_dir / "src_generated"

    def ensure_specs_dir(self) -> Path:
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        return self.specs_dir

    def ensure_extracted_specs_dir(self) -> Path:
        self.extracted_specs_dir.mkdir(parents=True, exist_ok=True)
        return self.extracted_specs_dir

    def ensure_generated_dir(self, target: str) -> Path:
        directory = self.generated_root_dir / normalize_target(target)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def resolve_spec_path(self, component_name: str) -> Path:
        """Return the canonical ``specs/<component>.amarooi`` path."""
        return self.ensure_specs_dir() / f"{_safe_component_name(component_name)}.amarooi"

    def resolve_extracted_spec_path(self, source_path: str | Path) -> Path:
        """Return the canonical extracted-spec JSON path for *source_path*."""
        return self.ensure_extracted_specs_dir() / f"{_spec_stem(source_path)}.amarooi.json"

    def resolve_generated_path(self, source_path: str | Path, target: str) -> Path:
        """Return the canonical target-isolated generated source path."""
        stem = _spec_stem(source_path)
        return self.ensure_generated_dir(target) / f"{stem}{target_extension(target)}"
