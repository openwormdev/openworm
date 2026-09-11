import unittest

from wormbrain.brain import _verified_reader_cache
from wormbrain.cect_reader import get_instance
from wormbrain.core import PLASTICITY


class ReaderTests(unittest.TestCase):
    def test_current_cect_reader_hash_and_named_plastic_family(self):
        self.assertEqual(_verified_reader_cache(), "98bdafffce1341d3443a83066a6225a977c8218c28c27d69e4bd465782bd4cc8")
        neurons, connections = get_instance().read_data(include_nonconnected_cells=True)
        self.assertGreater(len(neurons), 100)
        observed = {(connection.pre_cell, connection.post_cell) for connection in connections}
        expected = {tuple(path.split("->")) for path in PLASTICITY["paths"]}
        self.assertTrue(expected.issubset(observed))


if __name__ == "__main__":
    unittest.main()
