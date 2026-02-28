"""
Progress tracking utility module.

Per Constitution Principle VII (Performance Transparency),
provides progress indicators for operations >10 seconds.
"""

from collections.abc import Callable

from tqdm import tqdm


class ProgressTracker:
    """Progress tracking wrapper with tqdm integration."""

    def __init__(self, total: int, desc: str = "", unit: str = "item", show_bar: bool = True):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
            desc: Description of the operation
            unit: Unit name for items
            show_bar: Whether to show progress bar (True) or just log (False)
        """
        self.total = total
        self.desc = desc
        self.unit = unit
        self.current = 0
        self.show_bar = show_bar
        self._bar: tqdm | None = None

        if show_bar:
            self._bar = tqdm(
                total=total,
                desc=desc,
                unit=unit,
                ncols=80,
                bar_format="{desc}: [{bar}] {n_fmt}/{total_fmt} ({percentage:3.1f}%)",
            )

    def update(self, n: int = 1) -> None:
        """
        Update progress by n items.

        Args:
            n: Number of items processed
        """
        self.current += n
        if self._bar:
            self._bar.update(n)

    def set_description(self, desc: str) -> None:
        """Update progress description."""
        self.desc = desc
        if self._bar:
            self._bar.set_description(desc)

    def close(self) -> None:
        """Close progress tracker."""
        if self._bar:
            self._bar.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_progress_callback(
    total: int, desc: str = "Processing"
) -> tuple[Callable[[int, int], None], Callable[[], None]]:
    """
    Create a progress callback function and cleanup function.

    Args:
        total: Total number of items
        desc: Description of operation

    Returns:
        Tuple of (callback_function, cleanup_function)
    """
    tracker = ProgressTracker(total, desc)

    def callback(current: int, total_items: int) -> None:
        """Progress callback matching contract signature."""
        tracker.update(current - tracker.current)

    def cleanup() -> None:
        """Cleanup function to close progress bar."""
        tracker.close()

    return callback, cleanup


def wrap_with_progress(func: Callable, total: int, desc: str = "Processing", *args, **kwargs):
    """
    Wrapper function to execute a callable with progress tracking.

    Per T039, provides a convenient wrapper for functions that accept
    progress_callback parameter.

    Args:
        func: Function to execute (must accept progress_callback parameter)
        total: Total number of items to process
        desc: Description of operation
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func (excluding progress_callback)

    Returns:
        Result of func execution

    Example:
        result = wrap_with_progress(
            analyzer.analyze,
            total=1000,
            desc="Analyzing emails",
            corpus=my_corpus
        )
    """
    callback, cleanup = create_progress_callback(total, desc)

    try:
        kwargs["progress_callback"] = callback
        return func(*args, **kwargs)
    finally:
        cleanup()
