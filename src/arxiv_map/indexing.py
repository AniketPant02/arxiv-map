"""Dataset loading and indexing scaffolds for arXiv map inputs."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from .normalize import Normalizer # we will normalize arXiv IDs for indexing and lookup

class Dataset:
    """Base class for row-oriented datasets loaded from local JSON files."""

    dataset_name: str = "dataset"
    id_field: str | None = None
    is_json_lines: bool = False

    def __init__(self, dataset_path: str | Path) -> None:
        self.dataset_path = Path(dataset_path)
        self.dataset: list[dict[str, Any]] | None = None
        self.normalizer = Normalizer()

    def load(self) -> list[dict[str, Any]]:
        """Load all rows from the configured local file."""
        self.dataset = list(self._iter_file_rows())
        return self.dataset

    def iter_rows(self) -> Iterator[dict[str, Any]]:
        """Yield dataset rows one at a time."""
        rows = self.dataset if self.dataset is not None else self._iter_file_rows()
        for row in rows:
            yield row

    def iter_batches(self, batch_size: int) -> Iterator[list[dict[str, Any]]]:
        """Yield dataset rows in batches."""
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")

        batch: list[dict[str, Any]] = []
        for row in self.iter_rows():
            batch.append(row)
            if len(batch) == batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def find_by_ids(self, arxiv_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Return rows keyed by normalized arXiv ID."""
        # TODO: need to make this faster.
        if self.id_field is None:
            raise NotImplementedError(f"{type(self).__name__} must define id_field")

        target_ids = {self.normalizer.arxiv_id(arxiv_id) for arxiv_id in arxiv_ids}
        rows_by_id: dict[str, dict[str, Any]] = {}

        for row in self.iter_rows():
            row_id = row.get(self.id_field)
            if not isinstance(row_id, str):
                continue

            clean_row_id = self.normalizer.arxiv_id(row_id)
            if clean_row_id in target_ids:
                rows_by_id[clean_row_id] = row
                if len(rows_by_id) == len(target_ids):
                    break

        if not rows_by_id:
            print(f"Warning: None of the provided IDs were found in {self.dataset_name}")
            return {}

        return rows_by_id

    def _iter_file_rows(self) -> Iterator[dict[str, Any]]:
        """Yield rows from JSON-list or JSON-lines files."""
        if self.is_json_lines or self.dataset_path.suffix.lower() in {".jsonl", ".ndjson"}:
            yield from self._iter_json_lines()
            return

        with self.dataset_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            msg = (
                f"Expected {self.dataset_name} file to contain a list of rows, "
                f"got {type(data).__name__}"
            )
            raise ValueError(msg)

        for row in data:
            yield self._validate_row(row)

    def _iter_json_lines(self) -> Iterator[dict[str, Any]]:
        """Yield rows from a JSON-lines file without loading it all at once."""
        with self.dataset_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                yield self._validate_row(row, line_number=line_number)

    def _validate_row(self, row: Any, line_number: int | None = None) -> dict[str, Any]:
        if isinstance(row, dict):
            return row

        location = f" on line {line_number}" if line_number is not None else ""
        msg = (
            f"Expected {self.dataset_name} row{location} to be a dict, "
            f"got {type(row).__name__}"
        )
        raise ValueError(msg)


class ArxivMetadataIndex(Dataset):
    """Index local arXiv metadata snapshots and expose batch lookup helpers."""

    dataset_name = "arXiv metadata"
    id_field = "id"
    is_json_lines = True

    def __init__(self, metadata_path: str | Path) -> None:
        super().__init__(metadata_path)


class CometDataset(Dataset):
    """Load COMET affiliation extraction output from local files."""

    dataset_name = "COMET dataset"
    id_field = "arxiv_id"

    def __init__(self, dataset_path: str | Path) -> None:
        super().__init__(dataset_path)
