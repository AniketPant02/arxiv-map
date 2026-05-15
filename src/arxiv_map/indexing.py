"""Dataset loading and indexing scaffolds for arXiv map inputs."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


class ArxivMetadataIndex:
    """Index local arXiv metadata snapshots and expose batch lookup helpers."""

    def __init__(self, metadata_path: str | Path) -> None:
        self.metadata_path = Path(metadata_path)

    def iter_rows(self) -> Iterator[dict[str, Any]]:
        """Yield rows from a local arXiv metadata source."""
        raise NotImplementedError

    def find_by_ids(self, arxiv_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Return arXiv metadata rows keyed by normalized arXiv ID."""
        raise NotImplementedError

    def iter_batches(self, batch_size: int) -> Iterator[list[dict[str, Any]]]:
        """Yield arXiv metadata rows in batches."""
        raise NotImplementedError


class CometDataset:
    """Load COMET affiliation extraction output from local files."""

    def __init__(self, dataset_path: str | Path) -> None:
        self.dataset_path = Path(dataset_path)

    def load(self) -> list[dict[str, Any]]:
        """Load all COMET rows from the configured local file."""
        raise NotImplementedError

    def iter_rows(self) -> Iterator[dict[str, Any]]:
        """Yield COMET rows one at a time."""
        raise NotImplementedError

    def iter_batches(self, batch_size: int) -> Iterator[list[dict[str, Any]]]:
        """Yield COMET rows in batches."""
        raise NotImplementedError
