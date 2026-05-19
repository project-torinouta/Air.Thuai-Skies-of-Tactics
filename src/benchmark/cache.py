"""Results cache for re-plotting without re-running games."""

import json
import os
from typing import Dict, List, Optional, Tuple


RESULTS_CACHE = ".benchmark_cache.json"


def save_results_cache(
    results: Dict[str, List[int]],
) -> None:
    """Save per-game result sequences to a JSON cache.

    Keys are matchup labels (e.g. ``"sniper vs defensive"``), values are
    lists of game results (0=draw, 1=P1 wins, 2=P2 wins).

    :param results: Mapping of label → per-game result sequence.
    :type results: Dict[str, List[int]]
    """
    serializable: Dict[str, Dict[str, object]] = {}
    for label, seq in results.items():
        serializable[label] = {"sequence": seq}

    cache = {"results": serializable}
    with open(RESULTS_CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def load_results_cache() -> Optional[Dict[str, List[int]]]:
    """Load per-game result sequences from JSON cache.

    :returns: Mapping of label → per-game result sequence, or None.
    :rtype: Optional[Dict[str, List[int]]]
    """
    if not os.path.exists(RESULTS_CACHE):
        return None

    with open(RESULTS_CACHE) as f:
        cache = json.load(f)

    results: Dict[str, List[int]] = {}
    for label, val in cache["results"].items():
        results[label] = val["sequence"]

    return results
