"""State encoder — converts Environment to a fixed-size feature vector.

Always outputs 104 floats regardless of how many pieces are alive.
If fewer than 6 pieces exist, the trailing slots are zero-padded.
"""

from typing import List

import numpy as np

from env import Environment


MAX_PIECES = 6
FEATURES_PER_PIECE = 16
STATE_DIM = MAX_PIECES * FEATURES_PER_PIECE + MAX_PIECES + 2  # = 104


def _encode_piece(piece, bw: float, bh: float) -> List[float]:
    """Encode a single piece into a 16-dim feature vector.

    :param piece: A Piece object or None.
    :param bw: Board width in float.
    :param bh: Board height in float.
    :returns: 16 floats.
    :rtype: List[float]
    """
    if piece is None:
        return [0.0] * FEATURES_PER_PIECE
    p = piece.position
    return [
        float(piece.is_alive),
        float(piece.team - 1),
        float(p.x) / max(bw - 1, 1.0),
        float(p.y) / max(bh - 1, 1.0),
        float(piece.health) / max(float(piece.max_health), 1.0),
        float(piece.action_points) / max(float(piece.max_action_points), 1.0),
        float(piece.physical_damage) / 50.0,
        float(piece.physical_resist) / 30.0,
        float(piece.attack_range) / 15.0,
        float(piece.strength) / 30.0,
        float(piece.dexterity) / 30.0,
        float(piece.intelligence) / 30.0,
        float(piece.height) / 5.0,
        float(getattr(piece, 'weapon_type', 3)) / 4.0,
        float(getattr(piece, 'armour_type', 3)) / 3.0,
        float(piece.spell_slots) / max(float(piece.max_spell_slots), 1.0),
    ]


def encode_state(env: Environment) -> np.ndarray:
    """Encode the current environment state as a fixed-size feature vector.

    :param env: The game environment.
    :type env: Environment
    :returns: A 1-D numpy array of shape ``(104,)``.
    :rtype: np.ndarray
    """
    features: List[float] = []

    board = env.board
    bw = float(board.width) if board is not None else 20.0
    bh = float(board.height) if board is not None else 20.0

    queue = list(env.action_queue) if env.action_queue is not None else []

    # --- Per-piece features (padded to MAX_PIECES) ---
    for i in range(MAX_PIECES):
        if i < len(queue):
            features.extend(_encode_piece(queue[i], bw, bh))
        else:
            features.extend([0.0] * FEATURES_PER_PIECE)

    # --- Current piece indicator (one-hot over MAX_PIECES) ---
    current_id = env.current_piece.id if env.current_piece is not None else -1
    for i in range(MAX_PIECES):
        if i < len(queue) and queue[i] is not None and queue[i].id == current_id:
            features.append(1.0)
        else:
            features.append(0.0)

    # --- Global state ---
    features.append(float(env.round_number) / max(float(env.max_rounds), 1.0))
    features.append(float(env.is_game_over))

    return np.array(features, dtype=np.float32)


def state_dim() -> int:
    """Return the dimension of the encoded state vector.

    :returns: Feature vector length (always 104).
    :rtype: int
    """
    return STATE_DIM
