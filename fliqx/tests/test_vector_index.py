from __future__ import annotations

import numpy as np

from fliqx.vector.faiss_index import FaissVectorIndex


def test_vector_index_roundtrip() -> None:
    index = FaissVectorIndex(dimension=4, use_ann=False)
    index.add_batch(["a", "b"], np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32))

    result = index.search(np.array([[1, 0, 0, 0]], dtype=np.float32), top_k=1)
    assert result[0][0].user_id == "a"
    assert result[0][0].confidence > 0.9
