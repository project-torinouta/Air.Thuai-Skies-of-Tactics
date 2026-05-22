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

"""Sniper heuristic — STR 29 / DEX 1 / INT 0, formation spacing 6.

Uses the parameterised factory with specific knobs:
- ``target_mode=lowest_hp``
- ``formation_spacing=6.0``
- ``advance_mode=always``
- ``retreat_hp=0``
"""

from typing import Callable, List

from utils import ActionSet, PieceArg

_PAIR = None


def _get_pair():
    global _PAIR
    if _PAIR is None:
        from strategies.factory import make_strategy
        _PAIR = make_strategy(
            target_mode="lowest_hp",
            formation_spacing=6.0,
            advance_mode="always",
            retreat_hp=0,
        )
    return _PAIR


def get_sniper_heuristic_init_strategy() -> Callable[..., List[PieceArg]]:
    """Return the init strategy (standard 29/1/0 sniper)."""
    return _get_pair()[0]


def get_sniper_heuristic_action_strategy() -> Callable[..., ActionSet]:
    """Return the action strategy (lowest-hp, spacing 6, always advance)."""
    return _get_pair()[1]
