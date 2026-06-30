"""Eval layer smoke test: the layer exists and is selected only by -m eval."""

import pytest

pytestmark = pytest.mark.eval


def test_eval_layer_present() -> None:
    # Placeholder so the eval layer is real and separated. The DeepEval golden set
    # and the deterministic DAG gate replace this on Day 7.
    assert pytest.__version__
