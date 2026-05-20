# Copyright 2026 AshGrey <ashgrey.huaier@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the
# following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Average per-round indicator sequences across multiple matches for charting.

Reads pre-computed per-round sequences from ``compute_indicators`` output.
All computation lives in ``indicators.py`` — this module only aggregates.
"""

from math import sqrt
from typing import List


def average_timeline_sequences(all_indicators: List[dict]) -> dict:
    """Average per-round sequences across matches (mean ± std).

    All sequences within a metric are truncated to the shortest match length
    so every round position has the same sample size.

    :param all_indicators: List of dicts returned by ``compute_indicators``.
    :type all_indicators: List[dict]
    :returns: ``{"rounds": [1..N], metric: {camp: {"mean": [...], "std": [...]}}}``
        for each of ``compactness``, ``ffi``, ``kiting``.
    :rtype: dict
    """
    if not all_indicators:
        return {}

    # Determine shortest match length across all per-round sequences
    min_r = min(
        len(ind["player_compactness"])
        for ind in all_indicators
        if ind["player_compactness"]
    )
    if min_r < 2:
        return {}

    rounds = list(range(1, min_r + 1))
    result: dict = {"rounds": rounds}

    metrics = {
        "compactness": ("player_compactness", "opponent_compactness"),
        "ffi":         ("player_ffi", "opponent_ffi"),
        "kiting":      ("player_kiting_sequence", "opponent_kiting_sequence"),
    }

    for metric, (player_key, opponent_key) in metrics.items():
        result[metric] = {}
        for camp_key, camp_label in [(player_key, "Red"), (opponent_key, "Blue")]:
            series = [
                ind[camp_key][:min_r]
                for ind in all_indicators
                if camp_key in ind and ind[camp_key]
            ]
            if not series:
                continue
            means = []
            stds = []
            for r in range(min_r):
                vals = [s[r] for s in series]
                mu = sum(vals) / len(vals)
                means.append(mu)
                stds.append(_std(vals, mu))
            result[metric][camp_label] = {"mean": means, "std": stds}

    return result


def _std(vals: List[float], mu: float) -> float:
    """Population standard deviation (n, not n-1).

    :param vals: Sample values.
    :type vals: List[float]
    :param mu: Pre-computed mean of *vals*.
    :type mu: float
    :returns: Standard deviation.
    :rtype: float
    """
    return sqrt(sum((v - mu) ** 2 for v in vals) / len(vals)) if len(vals) > 1 else 0.0
