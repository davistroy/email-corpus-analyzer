"""
Unit tests for utility modules.

Tests cover:
- src/utils/paths.py - PathConfig class
- src/utils/file_manager.py - save_json, load_json, ensure_output_dir, atomic_write, atomic_write_text
- src/utils/progress.py - progress tracking utilities
- src/utils/logger.py - logging setup and error logging
"""
import json
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.utils.paths import PathConfig, get_output_dir, set_output_dir, ensure_output_dir
from src.utils.file_manager import (
    atomic_write,
    atomic_write_text,
    save_json,
    load_json,
    ensure_output_dir as fm_ensure_output_dir,
)
from src.utils.progress import (
    ProgressTracker,
    create_progress_callback,
    wrap_with_progress,
)
from src.utils.logger import setup_logger, get_logger, log_extraction_error


class TestPathConfig:
    """Test cases for PathConfig class."""

    def setup_method(self):
        """Reset PathConfig before each test."""
        PathConfig.reset_to_default()

    def teardown_method(self):
        """Reset PathConfig after each test."""
        PathConfig.reset_to_default()

    def test_get_default_output_dir_returns_home_data_outputs(self):
        """Test that default output directory is ~/data/outputs."""
        default_dir = PathConfig.get_default_output_dir()

        expected = Path.home() / "data" / "outputs"
        assert default_dir == expected

    def test_get_output_dir_returns_default_when_not_set(self):
        """Test that get_output_dir returns default when no override set."""
        output_dir = PathConfig.get_output_dir()

        assert output_dir == PathConfig.get_default_output_dir()

    def test_set_output_dir_with_path_object(self, tmp_path):
        """Test setting output directory with Path object."""
        custom_path = tmp_path / "custom_output"

        result = PathConfig.set_output_dir(custom_path)

        assert result == custom_path.resolve()
        assert PathConfig.get_output_dir() == custom_path.resolve()

    def test_set_output_dir_with_string(self, tmp_path):
        """Test setting output directory with string path."""
        custom_path = str(tmp_path / "string_output")

        result = PathConfig.set_output_dir(custom_path)

        assert result == Path(custom_path).resolve()
        assert PathConfig.get_output_dir() == Path(custom_path).resolve()

    def test_set_output_dir_resolves_relative_path(self):
        """Test that set_output_dir resolves relative paths to absolute."""
        relative_path = Path("relative/path")

        result = PathConfig.set_output_dir(relative_path)

        assert result.is_absolute()
        assert PathConfig.get_output_dir().is_absolute()

    def test_reset_to_default_clears_custom_path(self, tmp_path):
        """Test that reset_to_default clears custom output directory."""
        custom_path = tmp_path / "custom"
        PathConfig.set_output_dir(custom_path)

        PathConfig.reset_to_default()

        assert PathConfig.get_output_dir() == PathConfig.get_default_output_dir()

    def test_get_corpus_path(self, tmp_path):
        """Test get_corpus_path returns correct path."""
        PathConfig.set_output_dir(tmp_path)

        corpus_path = PathConfig.get_corpus_path()

        assert corpus_path == tmp_path / "email_corpus.json"

    def test_get_analysis_path(self, tmp_path):
        """Test get_analysis_path returns correct path."""
        PathConfig.set_output_dir(tmp_path)

        analysis_path = PathConfig.get_analysis_path()

        assert analysis_path == tmp_path / "corpus_analysis_results.json"

    def test_get_suggestions_path(self, tmp_path):
        """Test get_suggestions_path returns correct path."""
        PathConfig.set_output_dir(tmp_path)

        suggestions_path = PathConfig.get_suggestions_path()

        assert suggestions_path == tmp_path / "category_suggestions.json"

    def test_get_suggestions_report_path(self, tmp_path):
        """Test get_suggestions_report_path returns correct path."""
        PathConfig.set_output_dir(tmp_path)

        report_path = PathConfig.get_suggestions_report_path()

        assert report_path == tmp_path / "category_suggestions_report.md"

    def test_get_approved_categories_path(self, tmp_path):
        """Test get_approved_categories_path returns correct path."""
        PathConfig.set_output_dir(tmp_path)

        approved_path = PathConfig.get_approved_categories_path()

        assert approved_path == tmp_path / "approved_categories.json"

    def test_get_error_log_path(self, tmp_path):
        """Test get_error_log_path returns correct path."""
        PathConfig.set_output_dir(tmp_path)

        error_log_path = PathConfig.get_error_log_path()

        assert error_log_path == tmp_path / "extraction_errors.log"

    def test_get_checkpoint_path(self, tmp_path):
        """Test get_checkpoint_path returns correct path."""
        PathConfig.set_output_dir(tmp_path)

        checkpoint_path = PathConfig.get_checkpoint_path()

        assert checkpoint_path == tmp_path / "extraction_checkpoint.json"

    def test_ensure_output_dir_exists_creates_directory(self, tmp_path):
        """Test that ensure_output_dir_exists creates directory."""
        custom_dir = tmp_path / "new_output_dir"
        PathConfig.set_output_dir(custom_dir)

        result = PathConfig.ensure_output_dir_exists()

        assert result == custom_dir
        assert custom_dir.exists()
        assert custom_dir.is_dir()

    def test_ensure_output_dir_exists_sets_permissions(self, tmp_path):
        """Test that ensure_output_dir_exists sets 0700 permissions."""
        custom_dir = tmp_path / "secure_dir"
        PathConfig.set_output_dir(custom_dir)

        PathConfig.ensure_output_dir_exists()

        # Check permissions (on Unix-like systems)
        if os.name != 'nt':  # Skip on Windows
            mode = os.stat(custom_dir).st_mode & 0o777
            assert mode == 0o700

    def test_ensure_output_dir_exists_creates_parent_dirs(self, tmp_path):
        """Test that ensure_output_dir_exists creates parent directories."""
        nested_dir = tmp_path / "level1" / "level2" / "output"
        PathConfig.set_output_dir(nested_dir)

        PathConfig.ensure_output_dir_exists()

        assert nested_dir.exists()

    def test_ensure_output_dir_exists_idempotent(self, tmp_path):
        """Test that ensure_output_dir_exists can be called multiple times."""
        custom_dir = tmp_path / "idempotent_dir"
        PathConfig.set_output_dir(custom_dir)

        # Call twice
        result1 = PathConfig.ensure_output_dir_exists()
        result2 = PathConfig.ensure_output_dir_exists()

        assert result1 == result2
        assert custom_dir.exists()


class TestPathConfigConvenienceFunctions:
    """Test cases for convenience functions in paths module."""

    def setup_method(self):
        """Reset PathConfig before each test."""
        PathConfig.reset_to_default()

    def teardown_method(self):
        """Reset PathConfig after each test."""
        PathConfig.reset_to_default()

    def test_get_output_dir_function(self):
        """Test get_output_dir convenience function."""
        result = get_output_dir()

        assert result == PathConfig.get_output_dir()

    def test_set_output_dir_function(self, tmp_path):
        """Test set_output_dir convenience function."""
        custom_path = tmp_path / "convenience_test"

        result = set_output_dir(custom_path)

        assert result == custom_path.resolve()
        assert get_output_dir() == custom_path.resolve()

    def test_ensure_output_dir_function(self, tmp_path):
        """Test ensure_output_dir convenience function."""
        custom_path = tmp_path / "ensure_test"
        set_output_dir(custom_path)

        result = ensure_output_dir()

        assert result == custom_path
        assert custom_path.exists()


class TestFileManagerSaveJson:
    """Test cases for save_json function."""

    def test_save_json_creates_file(self, tmp_path):
        """Test that save_json creates a JSON file."""
        data = {"key": "value", "number": 42}
        file_path = tmp_path / "test.json"

        save_json(data, file_path)

        assert file_path.exists()

    def test_save_json_correct_content(self, tmp_path):
        """Test that save_json writes correct JSON content."""
        data = {"name": "test", "values": [1, 2, 3]}
        file_path = tmp_path / "test.json"

        save_json(data, file_path)

        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == data

    def test_save_json_with_string_path(self, tmp_path):
        """Test save_json with string path argument."""
        data = {"test": True}
        file_path = str(tmp_path / "string_path.json")

        save_json(data, file_path)

        assert Path(file_path).exists()

    def test_save_json_custom_indent(self, tmp_path):
        """Test save_json with custom indentation."""
        data = {"nested": {"key": "value"}}
        file_path = tmp_path / "indent.json"

        save_json(data, file_path, indent=4)

        content = file_path.read_text(encoding='utf-8')
        # Check that 4-space indent is used
        assert "    " in content

    def test_save_json_creates_parent_directories(self, tmp_path):
        """Test that save_json creates parent directories when needed."""
        data = {"test": "data"}
        file_path = tmp_path / "new_dir" / "subdir" / "file.json"

        save_json(data, file_path, ensure_parents=True)

        assert file_path.exists()

    def test_save_json_no_parent_creation(self, tmp_path):
        """Test save_json with ensure_parents=False raises error."""
        data = {"test": "data"}
        file_path = tmp_path / "nonexistent" / "file.json"

        with pytest.raises(FileNotFoundError):
            save_json(data, file_path, ensure_parents=False)

    def test_save_json_sets_permissions(self, tmp_path):
        """Test that save_json sets 0600 permissions."""
        data = {"secure": "data"}
        file_path = tmp_path / "secure.json"

        save_json(data, file_path)

        # Check permissions (on Unix-like systems)
        if os.name != 'nt':  # Skip on Windows
            mode = os.stat(file_path).st_mode & 0o777
            assert mode == 0o600

    def test_save_json_unicode_content(self, tmp_path):
        """Test save_json handles Unicode content correctly."""
        data = {"greeting": "Hello, World!", "special": "Special chars: < > &"}
        file_path = tmp_path / "unicode.json"

        save_json(data, file_path)

        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == data

    def test_save_json_overwrites_existing(self, tmp_path):
        """Test that save_json overwrites existing file."""
        file_path = tmp_path / "overwrite.json"
        save_json({"old": "data"}, file_path)

        save_json({"new": "data"}, file_path)

        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == {"new": "data"}

    def test_save_json_handles_non_serializable_with_default_str(self, tmp_path):
        """Test save_json uses default=str for non-serializable objects."""
        from datetime import datetime
        data = {"timestamp": datetime(2024, 1, 15, 10, 30, 0)}
        file_path = tmp_path / "datetime.json"

        save_json(data, file_path)

        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        # datetime should be converted to string
        assert isinstance(loaded["timestamp"], str)

    def test_save_json_empty_dict(self, tmp_path):
        """Test save_json with empty dictionary."""
        data = {}
        file_path = tmp_path / "empty.json"

        save_json(data, file_path)

        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == {}

    def test_save_json_list_data(self, tmp_path):
        """Test save_json with list as root element."""
        data = [1, 2, 3, "four", {"five": 5}]
        file_path = tmp_path / "list.json"

        save_json(data, file_path)

        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == data


class TestFileManagerLoadJson:
    """Test cases for load_json function."""

    def test_load_json_basic(self, tmp_path):
        """Test basic load_json functionality."""
        file_path = tmp_path / "test.json"
        expected = {"key": "value", "number": 123}
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(expected, f)

        result = load_json(file_path)

        assert result == expected

    def test_load_json_with_string_path(self, tmp_path):
        """Test load_json with string path argument."""
        file_path = tmp_path / "string.json"
        data = {"test": True}
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        result = load_json(str(file_path))

        assert result == data

    def test_load_json_file_not_found(self, tmp_path):
        """Test load_json raises FileNotFoundError for missing file."""
        nonexistent = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_json(nonexistent)

        assert "not found" in str(exc_info.value).lower()

    def test_load_json_invalid_json(self, tmp_path):
        """Test load_json raises JSONDecodeError for invalid JSON."""
        file_path = tmp_path / "invalid.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            load_json(file_path)

    def test_load_json_empty_file(self, tmp_path):
        """Test load_json with empty file raises JSONDecodeError."""
        file_path = tmp_path / "empty.json"
        file_path.touch()

        with pytest.raises(json.JSONDecodeError):
            load_json(file_path)

    def test_load_json_unicode_content(self, tmp_path):
        """Test load_json handles Unicode content."""
        file_path = tmp_path / "unicode.json"
        data = {"message": "Hello, World!"}
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

        result = load_json(file_path)

        assert result == data

    def test_load_json_nested_structure(self, tmp_path):
        """Test load_json with deeply nested structure."""
        file_path = tmp_path / "nested.json"
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        result = load_json(file_path)

        assert result == data

    def test_load_json_list_root(self, tmp_path):
        """Test load_json with list as root element."""
        file_path = tmp_path / "list.json"
        data = [1, "two", {"three": 3}]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        result = load_json(file_path)

        assert result == data


class TestFileManagerEnsureOutputDir:
    """Test cases for ensure_output_dir function from file_manager."""

    def setup_method(self):
        """Reset PathConfig before each test."""
        PathConfig.reset_to_default()

    def teardown_method(self):
        """Reset PathConfig after each test."""
        PathConfig.reset_to_default()

    def test_ensure_output_dir_with_none_uses_path_config(self, tmp_path):
        """Test ensure_output_dir with None uses PathConfig."""
        custom_dir = tmp_path / "path_config_dir"
        PathConfig.set_output_dir(custom_dir)

        result = fm_ensure_output_dir(None)

        assert result == custom_dir
        assert custom_dir.exists()

    def test_ensure_output_dir_with_custom_path(self, tmp_path):
        """Test ensure_output_dir with custom path."""
        custom_dir = tmp_path / "custom_dir"

        result = fm_ensure_output_dir(custom_dir)

        assert result == custom_dir
        assert custom_dir.exists()

    def test_ensure_output_dir_with_string_path(self, tmp_path):
        """Test ensure_output_dir with string path."""
        custom_dir = str(tmp_path / "string_dir")

        result = fm_ensure_output_dir(custom_dir)

        assert result == Path(custom_dir)
        assert Path(custom_dir).exists()

    def test_ensure_output_dir_sets_permissions(self, tmp_path):
        """Test ensure_output_dir sets 0700 permissions."""
        custom_dir = tmp_path / "secure_dir"

        fm_ensure_output_dir(custom_dir)

        if os.name != 'nt':  # Skip on Windows
            mode = os.stat(custom_dir).st_mode & 0o777
            assert mode == 0o700

    def test_ensure_output_dir_creates_nested_dirs(self, tmp_path):
        """Test ensure_output_dir creates parent directories."""
        nested_dir = tmp_path / "a" / "b" / "c"

        result = fm_ensure_output_dir(nested_dir)

        assert result == nested_dir
        assert nested_dir.exists()

    def test_ensure_output_dir_idempotent(self, tmp_path):
        """Test ensure_output_dir can be called multiple times."""
        custom_dir = tmp_path / "idempotent"

        result1 = fm_ensure_output_dir(custom_dir)
        result2 = fm_ensure_output_dir(custom_dir)

        assert result1 == result2


class TestAtomicWrite:
    """Test cases for atomic_write function (Work Item 3.4)."""

    def test_atomic_write_creates_file_with_text(self, tmp_path):
        """Test that atomic_write creates a file with text content."""
        file_path = tmp_path / "test.txt"

        atomic_write(file_path, "hello world")

        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == "hello world"

    def test_atomic_write_creates_file_with_bytes(self, tmp_path):
        """Test that atomic_write creates a file with bytes content."""
        file_path = tmp_path / "test.bin"
        content = b"\x00\x01\x02\x03"

        atomic_write(file_path, content)

        assert file_path.exists()
        assert file_path.read_bytes() == content

    def test_atomic_write_no_tmp_file_on_success(self, tmp_path):
        """Test that .tmp file is cleaned up after successful write."""
        file_path = tmp_path / "test.json"

        atomic_write(file_path, '{"key": "value"}')

        tmp_file = file_path.with_suffix(".json.tmp")
        assert not tmp_file.exists()
        assert file_path.exists()

    def test_atomic_write_preserves_existing_on_failure(self, tmp_path):
        """Test that existing file is NOT corrupted when write fails.

        This is the core guarantee: if the write process fails (e.g. disk
        full, serialization error, interrupt), the original file must remain
        intact.
        """
        file_path = tmp_path / "important.json"
        original_content = '{"original": "data"}'
        file_path.write_text(original_content, encoding="utf-8")

        # Force a failure during the write by making the tmp directory read-only
        # Actually, we'll simulate by patching os.replace to fail
        with patch("src.utils.file_manager.os.replace", side_effect=OSError("Simulated disk error")):
            with pytest.raises(OSError, match="Simulated disk error"):
                atomic_write(file_path, '{"corrupted": "data that should not appear"}')

        # Original file must be unchanged
        assert file_path.read_text(encoding="utf-8") == original_content

    def test_atomic_write_cleans_up_tmp_on_failure(self, tmp_path):
        """Test that .tmp file is removed when write fails."""
        file_path = tmp_path / "test.json"
        tmp_file = file_path.with_suffix(".json.tmp")

        with patch("src.utils.file_manager.os.replace", side_effect=OSError("fail")):
            with pytest.raises(OSError):
                atomic_write(file_path, "content")

        assert not tmp_file.exists()

    def test_atomic_write_overwrites_existing_file(self, tmp_path):
        """Test that atomic_write replaces existing file content."""
        file_path = tmp_path / "test.json"
        file_path.write_text("old content", encoding="utf-8")

        atomic_write(file_path, "new content")

        assert file_path.read_text(encoding="utf-8") == "new content"

    def test_atomic_write_with_string_path(self, tmp_path):
        """Test atomic_write works with string paths."""
        file_path = str(tmp_path / "string_path.txt")

        atomic_write(file_path, "string path content")

        assert Path(file_path).read_text(encoding="utf-8") == "string path content"

    def test_atomic_write_unicode_content(self, tmp_path):
        """Test atomic_write handles Unicode correctly."""
        file_path = tmp_path / "unicode.txt"
        content = "Hello \u4e16\u754c caf\u00e9 \u2603"

        atomic_write(file_path, content)

        assert file_path.read_text(encoding="utf-8") == content

    def test_atomic_write_large_content(self, tmp_path):
        """Test atomic_write with large content (simulates real corpus files)."""
        file_path = tmp_path / "large.json"
        # Create ~1MB of JSON content
        data = {"emails": [{"id": f"email_{i}", "body": "x" * 500} for i in range(1000)]}
        content = json.dumps(data, indent=2)

        atomic_write(file_path, content)

        loaded = json.loads(file_path.read_text(encoding="utf-8"))
        assert len(loaded["emails"]) == 1000

    def test_atomic_write_empty_content(self, tmp_path):
        """Test atomic_write with empty string content."""
        file_path = tmp_path / "empty.txt"

        atomic_write(file_path, "")

        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == ""


class TestAtomicWriteText:
    """Test cases for atomic_write_text function (Work Item 3.4)."""

    def test_atomic_write_text_creates_file(self, tmp_path):
        """Test that atomic_write_text creates a file."""
        file_path = tmp_path / "test.json"

        atomic_write_text(file_path, '{"test": true}')

        assert file_path.exists()
        assert json.loads(file_path.read_text(encoding="utf-8")) == {"test": True}

    def test_atomic_write_text_sets_permissions(self, tmp_path):
        """Test that atomic_write_text sets 0600 permissions."""
        file_path = tmp_path / "secure.json"

        atomic_write_text(file_path, "secure data")

        if os.name != "nt":  # Skip on Windows
            mode = os.stat(file_path).st_mode & 0o777
            assert mode == 0o600

    def test_atomic_write_text_preserves_existing_on_failure(self, tmp_path):
        """Test that existing file is preserved when atomic_write_text fails."""
        file_path = tmp_path / "important.json"
        original = '{"important": "data"}'
        file_path.write_text(original, encoding="utf-8")

        with patch("src.utils.file_manager.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                atomic_write_text(file_path, '{"bad": "data"}')

        assert file_path.read_text(encoding="utf-8") == original


class TestSaveJsonAtomic:
    """Test that save_json uses atomic writes (Work Item 3.4)."""

    def test_save_json_is_atomic_preserves_on_failure(self, tmp_path):
        """Test save_json preserves existing file on write failure.

        This verifies the atomic write integration: if save_json fails
        mid-write, the original file must not be corrupted.
        """
        file_path = tmp_path / "data.json"
        original_data = {"version": 1, "data": "original"}
        save_json(original_data, file_path)

        # Verify original was written
        assert load_json(file_path) == original_data

        # Now force a failure during the atomic replace
        with patch("src.utils.file_manager.os.replace", side_effect=OSError("disk error")):
            with pytest.raises(OSError):
                save_json({"version": 2, "data": "should not appear"}, file_path)

        # Original must survive
        assert load_json(file_path) == original_data

    def test_save_json_no_tmp_file_left(self, tmp_path):
        """Test that save_json does not leave .tmp files behind."""
        file_path = tmp_path / "clean.json"

        save_json({"clean": True}, file_path)

        tmp_file = file_path.with_suffix(".json.tmp")
        assert not tmp_file.exists()

    def test_save_json_no_tmp_file_on_failure(self, tmp_path):
        """Test that save_json cleans up .tmp file on failure."""
        file_path = tmp_path / "fail.json"
        tmp_file = file_path.with_suffix(".json.tmp")

        with patch("src.utils.file_manager.os.replace", side_effect=OSError("fail")):
            with pytest.raises(OSError):
                save_json({"data": "test"}, file_path)

        assert not tmp_file.exists()

    def test_save_json_roundtrip_still_works(self, tmp_path):
        """Test save_json/load_json roundtrip works with atomic writes."""
        file_path = tmp_path / "roundtrip.json"
        data = {
            "categories": [{"id": 1, "name": "Test"}],
            "metadata": {"version": "2.0"}
        }

        save_json(data, file_path)
        loaded = load_json(file_path)

        assert loaded == data


class TestProgressTracker:
    """Test cases for ProgressTracker class."""

    def test_progress_tracker_initialization(self):
        """Test ProgressTracker initializes with correct values."""
        tracker = ProgressTracker(total=100, desc="Test", unit="items")

        assert tracker.total == 100
        assert tracker.desc == "Test"
        assert tracker.unit == "items"
        assert tracker.current == 0
        assert tracker.show_bar is True

        tracker.close()

    def test_progress_tracker_no_bar(self):
        """Test ProgressTracker with show_bar=False."""
        tracker = ProgressTracker(total=50, desc="Silent", show_bar=False)

        assert tracker._bar is None
        assert tracker.show_bar is False

        tracker.close()

    def test_progress_tracker_update(self):
        """Test ProgressTracker update method."""
        tracker = ProgressTracker(total=100, show_bar=False)

        tracker.update(10)
        assert tracker.current == 10

        tracker.update(5)
        assert tracker.current == 15

        tracker.close()

    def test_progress_tracker_update_default_increment(self):
        """Test ProgressTracker update with default increment of 1."""
        tracker = ProgressTracker(total=100, show_bar=False)

        tracker.update()
        assert tracker.current == 1

        tracker.update()
        assert tracker.current == 2

        tracker.close()

    def test_progress_tracker_set_description(self):
        """Test ProgressTracker set_description method."""
        tracker = ProgressTracker(total=100, desc="Initial", show_bar=False)

        tracker.set_description("Updated")

        assert tracker.desc == "Updated"
        tracker.close()

    def test_progress_tracker_set_description_with_bar(self):
        """Test set_description updates tqdm bar."""
        tracker = ProgressTracker(total=100, desc="Initial", show_bar=True)

        tracker.set_description("New Description")

        assert tracker.desc == "New Description"
        tracker.close()

    def test_progress_tracker_context_manager(self):
        """Test ProgressTracker as context manager."""
        with ProgressTracker(total=50, show_bar=False) as tracker:
            tracker.update(10)
            assert tracker.current == 10

        # After exiting context, bar should be closed
        assert tracker._bar is None or tracker._bar.disable

    def test_progress_tracker_close_without_bar(self):
        """Test close method when no bar exists."""
        tracker = ProgressTracker(total=50, show_bar=False)

        # Should not raise any exception
        tracker.close()
        tracker.close()  # Double close should also be safe

    def test_progress_tracker_update_with_bar(self):
        """Test update method updates tqdm bar."""
        tracker = ProgressTracker(total=100, show_bar=True)

        tracker.update(25)

        assert tracker.current == 25
        assert tracker._bar.n == 25

        tracker.close()


class TestCreateProgressCallback:
    """Test cases for create_progress_callback function."""

    def test_create_progress_callback_returns_tuple(self):
        """Test that create_progress_callback returns callback and cleanup."""
        callback, cleanup = create_progress_callback(total=100, desc="Test")

        assert callable(callback)
        assert callable(cleanup)

        cleanup()

    def test_progress_callback_updates_progress(self):
        """Test that callback function updates progress correctly."""
        callback, cleanup = create_progress_callback(total=100, desc="Test")

        # Simulate progress updates
        callback(10, 100)
        callback(25, 100)
        callback(50, 100)

        cleanup()

    def test_progress_callback_handles_non_sequential_updates(self):
        """Test callback handles non-sequential progress updates."""
        callback, cleanup = create_progress_callback(total=100, desc="Test")

        # Jump from 0 to 50
        callback(50, 100)
        # Then to 75
        callback(75, 100)

        cleanup()

    def test_cleanup_function_closes_tracker(self):
        """Test that cleanup function properly closes the tracker."""
        callback, cleanup = create_progress_callback(total=100, desc="Test")

        # Use the callback
        callback(50, 100)

        # Cleanup should not raise
        cleanup()
        cleanup()  # Double cleanup should be safe


class TestWrapWithProgress:
    """Test cases for wrap_with_progress function."""

    def test_wrap_with_progress_basic(self):
        """Test wrap_with_progress executes function."""
        def sample_func(data, progress_callback=None):
            if progress_callback:
                progress_callback(50, 100)
            return data * 2

        result = wrap_with_progress(
            sample_func,
            total=100,
            desc="Processing",
            data=21
        )

        assert result == 42

    def test_wrap_with_progress_passes_kwargs(self):
        """Test wrap_with_progress passes keyword arguments."""
        def func_with_kwargs(a, b, multiplier=1, progress_callback=None):
            return (a + b) * multiplier

        result = wrap_with_progress(
            func_with_kwargs,
            total=50,
            desc="Test",
            a=10,
            b=5,
            multiplier=3
        )

        assert result == 45

    def test_wrap_with_progress_passes_args(self):
        """Test wrap_with_progress passes positional arguments."""
        def func_with_args(x, y, progress_callback=None):
            return x - y

        result = wrap_with_progress(
            func_with_args,
            total=100,
            desc="Subtract",
            x=100,
            y=30
        )

        assert result == 70

    def test_wrap_with_progress_cleanup_on_success(self):
        """Test that cleanup is called on successful execution."""
        cleanup_called = []

        def sample_func(progress_callback=None):
            return "success"

        with patch('src.utils.progress.create_progress_callback') as mock_create:
            mock_callback = MagicMock()
            mock_cleanup = MagicMock(side_effect=lambda: cleanup_called.append(True))
            mock_create.return_value = (mock_callback, mock_cleanup)

            result = wrap_with_progress(sample_func, total=10, desc="Test")

            assert result == "success"
            assert len(cleanup_called) == 1

    def test_wrap_with_progress_cleanup_on_exception(self):
        """Test that cleanup is called even when function raises exception."""
        cleanup_called = []

        def failing_func(progress_callback=None):
            raise ValueError("Test error")

        with patch('src.utils.progress.create_progress_callback') as mock_create:
            mock_callback = MagicMock()
            mock_cleanup = MagicMock(side_effect=lambda: cleanup_called.append(True))
            mock_create.return_value = (mock_callback, mock_cleanup)

            with pytest.raises(ValueError, match="Test error"):
                wrap_with_progress(failing_func, total=10, desc="Test")

            # Cleanup should still be called
            assert len(cleanup_called) == 1

    def test_wrap_with_progress_injects_callback(self):
        """Test that progress_callback is injected into kwargs."""
        received_callback = []

        def capture_callback(progress_callback=None):
            received_callback.append(progress_callback)
            return "done"

        wrap_with_progress(capture_callback, total=100, desc="Test")

        assert len(received_callback) == 1
        assert callable(received_callback[0])

    def test_wrap_with_progress_returns_none(self):
        """Test wrap_with_progress handles function returning None."""
        def func_returns_none(progress_callback=None):
            return None

        result = wrap_with_progress(func_returns_none, total=10, desc="Test")

        assert result is None

    def test_wrap_with_progress_complex_return(self):
        """Test wrap_with_progress handles complex return values."""
        def func_complex_return(progress_callback=None):
            return {"data": [1, 2, 3], "status": "ok"}

        result = wrap_with_progress(func_complex_return, total=10, desc="Test")

        assert result == {"data": [1, 2, 3], "status": "ok"}


class TestProgressTrackerEdgeCases:
    """Test edge cases for ProgressTracker."""

    def test_zero_total(self):
        """Test ProgressTracker with zero total items."""
        tracker = ProgressTracker(total=0, show_bar=False)

        assert tracker.total == 0
        tracker.update(0)
        assert tracker.current == 0

        tracker.close()

    def test_large_total(self):
        """Test ProgressTracker with large total."""
        tracker = ProgressTracker(total=1000000, show_bar=False)

        tracker.update(500000)
        assert tracker.current == 500000

        tracker.close()

    def test_negative_update(self):
        """Test ProgressTracker allows negative updates."""
        tracker = ProgressTracker(total=100, show_bar=False)

        tracker.update(50)
        tracker.update(-10)

        assert tracker.current == 40
        tracker.close()

    def test_empty_description(self):
        """Test ProgressTracker with empty description."""
        tracker = ProgressTracker(total=100, desc="", show_bar=False)

        assert tracker.desc == ""
        tracker.close()

    def test_special_characters_in_description(self):
        """Test ProgressTracker with special characters in description."""
        tracker = ProgressTracker(
            total=100,
            desc="Processing: [test] (100%)",
            show_bar=False
        )

        assert "Processing" in tracker.desc
        tracker.close()


class TestIntegration:
    """Integration tests combining multiple utilities."""

    def setup_method(self):
        """Reset PathConfig before each test."""
        PathConfig.reset_to_default()

    def teardown_method(self):
        """Reset PathConfig after each test."""
        PathConfig.reset_to_default()

    def test_save_and_load_json_roundtrip(self, tmp_path):
        """Test that save_json and load_json work together."""
        original_data = {
            "categories": [
                {"id": 1, "name": "Test"},
                {"id": 2, "name": "Example"}
            ],
            "metadata": {"version": "1.0"}
        }
        file_path = tmp_path / "roundtrip.json"

        save_json(original_data, file_path)
        loaded_data = load_json(file_path)

        assert loaded_data == original_data

    def test_path_config_with_file_manager(self, tmp_path):
        """Test PathConfig integration with file_manager functions."""
        # Set custom output directory
        PathConfig.set_output_dir(tmp_path)

        # Ensure directory exists
        output_dir = fm_ensure_output_dir(None)

        # Save file to corpus path
        corpus_path = PathConfig.get_corpus_path()
        test_data = {"emails": ["test@example.com"]}
        save_json(test_data, corpus_path)

        # Load and verify
        loaded = load_json(corpus_path)
        assert loaded == test_data
        assert corpus_path.parent == output_dir

    def test_progress_with_file_operations(self, tmp_path):
        """Test progress tracking with file operations."""
        def process_files(files, progress_callback=None):
            results = []
            for i, file_data in enumerate(files):
                if progress_callback:
                    progress_callback(i + 1, len(files))
                file_path = tmp_path / f"file_{i}.json"
                save_json(file_data, file_path)
                results.append(file_path)
            return results

        files_to_process = [
            {"id": 1, "value": "a"},
            {"id": 2, "value": "b"},
            {"id": 3, "value": "c"}
        ]

        result = wrap_with_progress(
            process_files,
            total=len(files_to_process),
            desc="Processing files",
            files=files_to_process
        )

        assert len(result) == 3
        for path in result:
            assert path.exists()


class TestSetupLogger:
    """Test cases for setup_logger function."""

    def teardown_method(self):
        """Clean up loggers after each test to avoid handler accumulation."""
        # Remove all handlers from test loggers
        for name in ['test_logger', 'test_file_logger', 'extraction_errors']:
            logger = logging.getLogger(name)
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_setup_logger_basic(self):
        """Test basic logger setup without file handler."""
        logger = setup_logger('test_logger')

        assert logger.name == 'test_logger'
        assert logger.level == logging.DEBUG
        # Should have console handler
        assert len(logger.handlers) >= 1

    def test_setup_logger_with_file_handler(self, tmp_path):
        """Test logger setup with file handler creates log file."""
        log_file = tmp_path / "logs" / "test.log"

        logger = setup_logger('test_file_logger', log_file=log_file)

        # Verify file handler was added
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1

        # Write a log message
        logger.debug("Test debug message")

        # Verify log file was created
        assert log_file.exists()

    def test_setup_logger_file_handler_format(self, tmp_path):
        """Test that file handler uses detailed format with timestamp."""
        log_file = tmp_path / "detailed.log"

        logger = setup_logger('test_file_logger', log_file=log_file)
        logger.debug("Test message for format")

        # Read log file content
        content = log_file.read_text(encoding='utf-8')

        # Should contain timestamp format YYYY-MM-DD HH:MM:SS
        assert " - test_file_logger - DEBUG - " in content

    def test_setup_logger_creates_parent_directories(self, tmp_path):
        """Test that setup_logger creates parent directories for log file."""
        log_file = tmp_path / "deep" / "nested" / "path" / "app.log"

        logger = setup_logger('test_file_logger', log_file=log_file)
        logger.info("Test message")

        assert log_file.parent.exists()
        assert log_file.exists()

    def test_setup_logger_avoids_duplicate_handlers(self, tmp_path):
        """Test that calling setup_logger twice doesn't add duplicate handlers."""
        log_file = tmp_path / "duplicate.log"

        # First call
        logger1 = setup_logger('test_file_logger', log_file=log_file)
        handler_count_1 = len(logger1.handlers)

        # Second call should return same logger without adding handlers
        logger2 = setup_logger('test_file_logger', log_file=log_file)
        handler_count_2 = len(logger2.handlers)

        assert logger1 is logger2
        assert handler_count_1 == handler_count_2

    def test_setup_logger_custom_level(self):
        """Test logger with custom logging level."""
        logger = setup_logger('test_logger', level=logging.WARNING)

        assert logger.level == logging.WARNING


class TestGetLogger:
    """Test cases for get_logger function."""

    def teardown_method(self):
        """Clean up loggers after each test."""
        logger = logging.getLogger('get_test_logger')
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def test_get_logger_returns_configured_logger(self):
        """Test that get_logger returns a configured logger."""
        logger = get_logger('get_test_logger')

        assert logger.name == 'get_test_logger'
        assert logger.level == logging.DEBUG

    def test_get_logger_with_log_file(self, tmp_path):
        """Test get_logger with log file parameter."""
        log_file = tmp_path / "get_logger.log"

        logger = get_logger('get_test_logger', log_file=log_file)
        logger.debug("Test message")

        assert log_file.exists()


class TestLogExtractionError:
    """Test cases for log_extraction_error function."""

    def teardown_method(self):
        """Clean up extraction_errors logger after each test."""
        logger = logging.getLogger('extraction_errors')
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def test_log_extraction_error_creates_log_file(self, tmp_path):
        """Test that log_extraction_error creates the log file."""
        log_file = tmp_path / "errors.log"

        log_extraction_error(
            email_id="test_email_123",
            error_type="rate_limit",
            error_message="API rate limit exceeded",
            log_file=log_file
        )

        assert log_file.exists()

    def test_log_extraction_error_format(self, tmp_path):
        """Test that log_extraction_error uses structured format."""
        log_file = tmp_path / "structured_errors.log"

        log_extraction_error(
            email_id="email_456",
            error_type="timeout",
            error_message="Connection timed out after 30s",
            log_file=log_file
        )

        content = log_file.read_text(encoding='utf-8')

        # Verify structured format
        assert "email_id=email_456" in content
        assert "error_type=timeout" in content
        assert "message=Connection timed out after 30s" in content

    def test_log_extraction_error_creates_parent_directories(self, tmp_path):
        """Test that log_extraction_error creates parent directories."""
        log_file = tmp_path / "nested" / "dir" / "extraction.log"

        log_extraction_error(
            email_id="email_789",
            error_type="malformed",
            error_message="Invalid email format",
            log_file=log_file
        )

        assert log_file.parent.exists()
        assert log_file.exists()

    def test_log_extraction_error_appends_multiple(self, tmp_path):
        """Test that multiple errors are appended to the same file."""
        log_file = tmp_path / "multi_errors.log"

        log_extraction_error(
            email_id="email_1",
            error_type="rate_limit",
            error_message="First error",
            log_file=log_file
        )
        log_extraction_error(
            email_id="email_2",
            error_type="unknown",
            error_message="Second error",
            log_file=log_file
        )

        content = log_file.read_text(encoding='utf-8')

        assert "email_id=email_1" in content
        assert "email_id=email_2" in content

    def test_log_extraction_error_default_log_file(self, tmp_path, monkeypatch):
        """Test log_extraction_error with default log file path."""
        # Change to tmp_path to control where default log goes
        monkeypatch.chdir(tmp_path)

        log_extraction_error(
            email_id="default_test",
            error_type="test",
            error_message="Testing default path"
        )

        default_log = tmp_path / "outputs" / "extraction_errors.log"
        assert default_log.exists()


class TestSharedTextWordLists:
    """Tests for src.utils.text shared word lists.

    Verifies that the unified word lists contain every word that was
    previously defined independently in name_generator.py,
    subject_analyzer.py, and category_generator.py.
    """

    def test_stop_words_contains_all_name_generator_words(self):
        """Shared STOP_WORDS must contain every word from the old name_generator list."""
        from src.utils.text import STOP_WORDS

        old_name_generator_stops = frozenset([
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare", "ought",
            "used", "this", "that", "these", "those", "i", "you", "he", "she", "it",
            "we", "they", "what", "which", "who", "whom", "whose", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more", "most",
            "other", "some", "such", "no", "not", "only", "same", "so", "than",
            "too", "very", "just", "also", "now", "here", "there", "then", "once",
            "email", "emails", "mail", "message", "messages", "subject", "re", "fwd",
            "fw", "sent", "received", "please", "thanks", "thank", "regards", "hi",
            "hello", "dear", "sincerely", "best", "am", "pm", "your", "our", "my",
        ])

        missing = old_name_generator_stops - STOP_WORDS
        assert not missing, f"Words missing from shared STOP_WORDS: {missing}"

    def test_stop_words_contains_all_subject_analyzer_words(self):
        """Shared STOP_WORDS must contain every word from the old subject_analyzer list."""
        from src.utils.text import STOP_WORDS

        old_subject_analyzer_stops = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'you', 'your', 'have', 'this', 'but',
            'or', 'not', 'can', 'we', 'all', 'been', 'were', 'when', 'what',
            'which', 'who', 'if', 'out', 'so', 'up', 'there', 'their', 'they',
            'me', 'my', 'our', 'us', 'am', 'i', 'them',
        }

        missing = old_subject_analyzer_stops - STOP_WORDS
        assert not missing, f"Words missing from shared STOP_WORDS: {missing}"

    def test_stop_words_contains_all_category_generator_words(self):
        """Shared STOP_WORDS must contain every word from the old category_generator list."""
        from src.utils.text import STOP_WORDS

        old_category_generator_stops = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
            'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
            'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
            'than', 'too', 'very', 'just', 'your', 'our', 'my', 'for', 'and',
            'but', 'or', 'of', 'to', 'in', 'on', 'at', 'by', 'from', 'with',
            're', 'fwd', 'fw',
        }

        missing = old_category_generator_stops - STOP_WORDS
        assert not missing, f"Words missing from shared STOP_WORDS: {missing}"

    def test_stop_words_is_frozenset(self):
        """STOP_WORDS must be a frozenset to prevent accidental mutation."""
        from src.utils.text import STOP_WORDS
        assert isinstance(STOP_WORDS, frozenset)

    def test_generic_words_contains_all_original_words(self):
        """Shared GENERIC_WORDS must contain all original name_generator words."""
        from src.utils.text import GENERIC_WORDS

        original = frozenset([
            "category", "related", "miscellaneous", "other", "various", "general",
            "stuff", "things", "items", "emails", "messages", "mail", "type", "kind",
        ])
        missing = original - GENERIC_WORDS
        assert not missing, f"Words missing from shared GENERIC_WORDS: {missing}"

    def test_generic_words_is_frozenset(self):
        """GENERIC_WORDS must be a frozenset."""
        from src.utils.text import GENERIC_WORDS
        assert isinstance(GENERIC_WORDS, frozenset)

    def test_action_words_contains_all_original_words(self):
        """Shared ACTION_WORDS must contain all original name_generator words."""
        from src.utils.text import ACTION_WORDS

        original = frozenset([
            "update", "updates", "notification", "notifications", "alert", "alerts",
            "confirmation", "confirmations", "reminder", "reminders", "request",
            "requests", "shipping", "shipped", "delivery", "delivered", "payment",
            "paid", "invoice", "invoiced", "order", "ordered", "receipt", "report",
            "reports", "summary", "weekly", "daily", "monthly", "newsletter",
        ])
        missing = original - ACTION_WORDS
        assert not missing, f"Words missing from shared ACTION_WORDS: {missing}"

    def test_action_words_is_frozenset(self):
        """ACTION_WORDS must be a frozenset."""
        from src.utils.text import ACTION_WORDS
        assert isinstance(ACTION_WORDS, frozenset)

    def test_known_proper_nouns_contains_all_original_words(self):
        """Shared KNOWN_PROPER_NOUNS must contain all original name_generator brands."""
        from src.utils.text import KNOWN_PROPER_NOUNS

        original = frozenset([
            "amazon", "google", "microsoft", "apple", "facebook", "twitter", "linkedin",
            "github", "slack", "zoom", "netflix", "spotify", "uber", "lyft", "paypal",
            "venmo", "chase", "wells", "fargo", "citi", "capital", "american", "express",
            "mastercard", "visa", "discover", "walmart", "target", "costco", "ebay",
            "etsy", "shopify", "stripe", "square", "dropbox", "box", "salesforce",
            "hubspot", "mailchimp", "constant", "contact", "sendgrid", "twilio",
        ])
        missing = original - KNOWN_PROPER_NOUNS
        assert not missing, f"Words missing from shared KNOWN_PROPER_NOUNS: {missing}"

    def test_known_proper_nouns_is_frozenset(self):
        """KNOWN_PROPER_NOUNS must be a frozenset."""
        from src.utils.text import KNOWN_PROPER_NOUNS
        assert isinstance(KNOWN_PROPER_NOUNS, frozenset)

    def test_module_specific_extension_pattern(self):
        """Verify modules can extend shared sets without mutating the original."""
        from src.utils.text import STOP_WORDS

        original_len = len(STOP_WORDS)
        extended = STOP_WORDS | {"custom_module_word"}

        assert "custom_module_word" in extended
        assert "custom_module_word" not in STOP_WORDS
        assert len(STOP_WORDS) == original_len

    def test_name_generator_imports_from_shared(self):
        """Verify name_generator uses the shared word lists, not local ones."""
        import src.generators.name_generator as ng
        from src.utils.text import (
            ACTION_WORDS,
            GENERIC_WORDS,
            KNOWN_PROPER_NOUNS,
            STOP_WORDS,
        )

        assert ng.STOP_WORDS is STOP_WORDS
        assert ng.GENERIC_WORDS is GENERIC_WORDS
        assert ng.ACTION_WORDS is ACTION_WORDS
        assert ng.KNOWN_PROPER_NOUNS is KNOWN_PROPER_NOUNS

    def test_subject_analyzer_uses_shared_stop_words(self):
        """Verify SubjectAnalyzer.STOP_WORDS references the shared set."""
        from src.analyzers.subject_analyzer import SubjectAnalyzer
        from src.utils.text import STOP_WORDS

        assert SubjectAnalyzer.STOP_WORDS is STOP_WORDS
