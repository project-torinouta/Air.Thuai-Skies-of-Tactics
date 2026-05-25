"""Gym environment wrapping the THUAI9 game engine.

Observation: 104-dim float vector from ml.state_encoder.
Action: 6-dim continuous in [-1, 1] — meta-parameters for action_decoder.
Reward: HP-difference change per step + terminal ±10 for win/loss.
"""

import contextlib
import os
from typing import Callable, List, Optional, Tuple

import numpy as np

from env import Environment
from ml.action_decoder import decode_action
from ml.state_encoder import encode_state, state_dim
from strategies.child6 import (
    get_child6_action_strategy,
    get_child6_init_strategy,
)
from strategies.sniper import get_sniper_init_strategy
from utils import ActionSet


class BattleEnv:
    """Gym-like environment for a single P1 (RL) vs P2 (fixed) game.

    Not a full Gymnasium implementation — just the subset we need.
    Supports reset(), step(), render().
    """

    def __init__(
        self,
        board_file: str = "./BoardCase/case1.txt",
        opponent_action_strategy: Optional[Callable] = None,
        opponent_init_strategy: Optional[Callable] = None,
        suppress_stdout: bool = True,
    ):
        self.board_file = board_file
        self.suppress_stdout = suppress_stdout

        self._opponent_action = (
            opponent_action_strategy
            if opponent_action_strategy is not None
            else get_child6_action_strategy()
        )
        self._opponent_init = (
            opponent_init_strategy
            if opponent_init_strategy is not None
            else get_child6_init_strategy()
        )
        self._p1_init = get_sniper_init_strategy()

        self.env: Optional[Environment] = None
        self.obs_dim = state_dim()
        self.action_dim = 6  # meta-parameters for action_decoder

    def reset(self) -> np.ndarray:
        """Start a new game. Returns initial observation."""
        self.env = Environment(local_mode=True, if_log=0)

        # P1 = RL policy (action set in step())
        # P2 = fixed opponent
        p1_action = lambda e: ActionSet()  # dummy, overridden in step()
        self.env.input_manager.set_function_input_method(
            1, self._p1_init, p1_action,
        )
        self.env.input_manager.set_function_input_method(
            2, self._opponent_init, self._opponent_action,
        )

        try:
            with open(os.devnull, "w") as sink:
                with contextlib.redirect_stdout(sink):
                    self.env.initialize(self.board_file)
        except Exception:
            self.env = None
            return np.zeros(self.obs_dim, dtype=np.float32)

        self._prev_hp_diff = self._hp_diff()
        return self._get_obs()

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, dict]:
        """Execute one RL step.

        1. Decode action → ActionSet and apply.
        2. Step through opponent turns until our turn again or game over.
        3. Return (obs, reward, done, info).

        Reward = HP-diff Δ (normalised) + terminal ±10.
        """
        if self.env is None or self.env.is_game_over:
            return np.zeros(self.obs_dim, dtype=np.float32), 0.0, True, {}

        hp_before = self._hp_diff()

        # 1. Decode and apply our action
        # PPO outputs are in [-1, 1], action_decoder expects [-2, 2]
        logits = np.clip(action, -1.0, 1.0) * 2.0
        our_act = decode_action(logits, self.env)
        self._apply(our_act)

        # 2. Step opponent turns until it's our turn again
        while not self.env.is_game_over:
            cp = self.env.current_piece
            if cp is not None and cp.team == 1:
                break
            self._step_env()

        hp_after = self._hp_diff()
        reward = float(hp_after - hp_before) / 50.0  # normalise

        # 3. Terminal reward
        done = self.env.is_game_over
        if done:
            p1_alive = any(p.is_alive for p in self.env.player1.pieces)
            p2_alive = any(p.is_alive for p in self.env.player2.pieces)
            if p1_alive and not p2_alive:
                reward += 10.0
            elif not p1_alive and p2_alive:
                reward -= 10.0

        return self._get_obs(), reward, done, {}

    def render(self, mode: str = "ascii") -> None:
        """Print the current board state."""
        if self.env is not None:
            from board_visual import visualize_board
            visualize_board(self.env)

    # ── helpers ──────────────────────────────────────────────────────

    def _get_obs(self) -> np.ndarray:
        if self.env is None:
            return np.zeros(self.obs_dim, dtype=np.float32)
        return encode_state(self.env)

    def _hp_diff(self) -> float:
        if self.env is None:
            return 0.0
        p1_hp = sum(
            p.health for p in self.env.player1.pieces if p.is_alive
        )
        p2_hp = sum(
            p.health for p in self.env.player2.pieces if p.is_alive
        )
        return p1_hp - p2_hp

    def _apply(self, act: ActionSet) -> None:
        """Apply an ActionSet using the env internals."""
        try:
            with open(os.devnull, "w") as sink:
                with contextlib.redirect_stdout(sink):
                    self.env.execute_player_action(act)
        except Exception:
            pass

    def _step_env(self) -> None:
        """Single env.step() with stdout suppressed."""
        try:
            with open(os.devnull, "w") as sink:
                with contextlib.redirect_stdout(sink):
                    self.env.step()
        except Exception:
            pass
