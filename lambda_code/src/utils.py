from __future__ import annotations

import json
from itertools import batched
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable, Generator


class DataPipeline:
    def __init__(self, data_generator: Generator[dict, None, None]):
        """Create a data pipeline from a generator."""

        self._data = data_generator

    def apply(self, func: Callable[[dict], dict]) -> DataPipeline:
        """Apply a function to each document in the data pipeline."""

        self._data = (func(doc) for doc in self._data)
        return self

    def apply_expand(self, func: Callable[[dict], list[dict]]) -> DataPipeline:
        """Apply a function that expands a document into multiple documents."""

        self._data = (doc for doc in self._data for doc in func(doc))
        return self

    def apply_batch(self, func: Callable[[tuple[dict, ...]], tuple[dict, ...]], batch_size: int) -> DataPipeline:
        """Apply a function to a batch of documents."""

        self._data = (doc for batch in batched(self._data, batch_size) for doc in func(batch))
        return self

    def collect(self) -> list[dict]:
        """Collect the data pipeline into a list."""

        return list(self._data)

    def to_jsonl(self) -> str:
        """Convert the data pipeline to a JSONL string."""

        return "\n".join([json.dumps(doc) for doc in self._data])
