"""Tests for dependency declarations in pyproject.toml.

Work Item 2.4: Verify that instructor, openai, and anthropic (optional)
dependencies are properly declared and installable.

Work Item 4.4: Verify that sqlite-vec dependency is properly declared,
version-pinned, and importable for vector similarity search.
"""

import importlib
import pathlib

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

import pytest


@pytest.fixture
def pyproject_data():
    """Load and parse pyproject.toml."""
    project_root = pathlib.Path(__file__).parent.parent.parent
    pyproject_path = project_root / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml not found at project root"
    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


class TestCoreDependencies:
    """Verify core dependencies are declared in pyproject.toml."""

    def test_instructor_in_dependencies(self, pyproject_data):
        """instructor>=1.0.0 must be in [project.dependencies]."""
        deps = pyproject_data["project"]["dependencies"]
        instructor_deps = [d for d in deps if d.startswith("instructor")]
        assert len(instructor_deps) == 1, "instructor should appear exactly once in dependencies"
        assert ">=1.0.0" in instructor_deps[0], "instructor version should be >=1.0.0"

    def test_openai_in_dependencies(self, pyproject_data):
        """openai>=1.0.0 must be in [project.dependencies]."""
        deps = pyproject_data["project"]["dependencies"]
        openai_deps = [d for d in deps if d.startswith("openai")]
        assert len(openai_deps) == 1, "openai should appear exactly once in dependencies"
        assert ">=1.0.0" in openai_deps[0], "openai version should be >=1.0.0"

    def test_instructor_importable(self):
        """instructor package must be importable after install."""
        mod = importlib.import_module("instructor")
        assert mod is not None

    def test_openai_importable(self):
        """openai package must be importable after install."""
        mod = importlib.import_module("openai")
        assert mod is not None


class TestOptionalCloudDependencies:
    """Verify cloud optional dependencies are declared in pyproject.toml."""

    def test_cloud_extra_exists(self, pyproject_data):
        """[project.optional-dependencies] must have a 'cloud' extra."""
        optional = pyproject_data["project"]["optional-dependencies"]
        assert "cloud" in optional, "'cloud' extra must exist in optional-dependencies"

    def test_anthropic_in_cloud_extra(self, pyproject_data):
        """anthropic>=0.30.0 must be in the 'cloud' extra."""
        cloud_deps = pyproject_data["project"]["optional-dependencies"]["cloud"]
        anthropic_deps = [d for d in cloud_deps if d.startswith("anthropic")]
        assert len(anthropic_deps) == 1, "anthropic should appear exactly once in cloud extra"
        assert ">=0.30.0" in anthropic_deps[0], "anthropic version should be >=0.30.0"


class TestRequirementsTxt:
    """Verify requirements.txt is consistent with pyproject.toml."""

    def test_instructor_in_requirements(self):
        """instructor must appear in requirements.txt."""
        project_root = pathlib.Path(__file__).parent.parent.parent
        requirements_path = project_root / "requirements.txt"
        content = requirements_path.read_text()
        assert "instructor>=1.0.0" in content, "instructor>=1.0.0 missing from requirements.txt"

    def test_openai_in_requirements(self):
        """openai must appear in requirements.txt."""
        project_root = pathlib.Path(__file__).parent.parent.parent
        requirements_path = project_root / "requirements.txt"
        content = requirements_path.read_text()
        assert "openai>=1.0.0" in content, "openai>=1.0.0 missing from requirements.txt"


class TestSqliteVecDependency:
    """Verify sqlite-vec dependency is declared and installable (Work Item 4.4)."""

    def test_sqlite_vec_in_dependencies(self, pyproject_data):
        """sqlite-vec>=0.1.0 must be in [project.dependencies]."""
        deps = pyproject_data["project"]["dependencies"]
        sqlite_vec_deps = [d for d in deps if d.startswith("sqlite-vec")]
        assert len(sqlite_vec_deps) == 1, "sqlite-vec should appear exactly once in dependencies"
        assert ">=0.1.0" in sqlite_vec_deps[0], "sqlite-vec version should be >=0.1.0"

    def test_sqlite_vec_importable(self):
        """sqlite_vec package must be importable after install."""
        mod = importlib.import_module("sqlite_vec")
        assert mod is not None

    def test_sqlite_vec_loadable_in_sqlite(self):
        """sqlite-vec extension must load into an in-memory SQLite connection."""
        import sqlite3

        import sqlite_vec

        db = sqlite3.connect(":memory:")
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        # Verify vec_version() function is available
        version = db.execute("SELECT vec_version()").fetchone()[0]
        assert version, "vec_version() should return a non-empty version string"
        db.close()

    def test_sqlite_vec_in_requirements_txt(self):
        """sqlite-vec must appear in requirements.txt."""
        project_root = pathlib.Path(__file__).parent.parent.parent
        requirements_path = project_root / "requirements.txt"
        content = requirements_path.read_text()
        assert "sqlite-vec>=0.1.0" in content, "sqlite-vec>=0.1.0 missing from requirements.txt"


class TestNoDependencyConflicts:
    """Verify no dependency conflicts exist."""

    def test_existing_dependencies_still_present(self, pyproject_data):
        """Existing dependencies must not be removed or altered."""
        deps = pyproject_data["project"]["dependencies"]
        dep_names = [d.split(">=")[0].split("[")[0].strip() for d in deps]

        # All pre-existing core deps must still be present
        expected = [
            "sentence-transformers",
            "scikit-learn",
            "beautifulsoup4",
            "lxml",
            "tqdm",
            "pydantic",
            "numpy",
            "pyyaml",
            "textual",
            "jinja2",
            "msal",
            "requests",
            "google-auth",
            "google-auth-oauthlib",
            "google-api-python-client",
        ]
        for pkg in expected:
            assert pkg in dep_names, f"Existing dependency '{pkg}' must not be removed"

    def test_dev_dependencies_still_present(self, pyproject_data):
        """Dev optional dependencies must not be removed or altered."""
        dev_deps = pyproject_data["project"]["optional-dependencies"]["dev"]
        dep_names = [d.split(">=")[0].split("[")[0].strip() for d in dev_deps]
        expected = ["pytest", "pytest-cov", "ruff", "mypy", "types-requests", "types-PyYAML"]
        for pkg in expected:
            assert pkg in dep_names, f"Existing dev dependency '{pkg}' must not be removed"
