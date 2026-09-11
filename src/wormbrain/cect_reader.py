"""Compatibility adapter from c302 0.12 to the pinned current CECT reader."""
from __future__ import annotations

from cect.readers.Cook2019HermReader import get_instance as get_cect_instance


class Cook2019HermAdapter:
    def __init__(self):
        self.reader = get_cect_instance(from_cache=True)

    def read_data(self, *, include_nonconnected_cells=False):
        # Cook2019 already returns its complete neuronal dataset; its 0.3.4
        # method predates this c302 compatibility keyword.
        return self.reader._read_data()

    def read_muscle_data(self):
        return self.reader._read_muscle_data()


def get_instance():
    return Cook2019HermAdapter()
