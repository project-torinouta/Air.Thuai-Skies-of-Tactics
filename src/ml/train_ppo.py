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

"""Train a policy using PPO with self-play.

Usage:
    uv run python -m ml.train_ppo --epochs 100 --games 32 --opponent sniper
    uv run python -m ml.train_ppo --epochs 10 --games 4 --opponent sniper  # smoke
"""

import argparse
import glob
import os
import sys
import time
from typing import Callable, List, Optional, Tuple

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.action_decoder_ppo import decode_ppo_action
from ml.ppo import PPOPolicy, RolloutBuffer, update_policy, DEVICE as _DEVICE
from ml.state_encoder import encode_state


WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "..", "weights")


#
# Trajectory recording wrapper
#


class PPOTrajectoryLogger:
    """Wraps a PPO policy to record trajectories during game play."""

    def __init__(self, policy: PPOPolicy, gamma: float = 0.99):
        self.policy = policy
        self.gamma = gamma
        self.buffer = RolloutBuffer()
        self._step_rewards: List[float] = []

    def action_strategy(self, env) -> "ActionSet":
        from utils import ActionSet
        state = encode_state(env)
        action, log_prob, _ = self.policy.sample_action(state)

        # Estimate value for this state
        state_t = torch.FloatTensor(state).unsqueeze(0).to(
            torch.device("cuda" if torch.cuda.is_available() else "cpu"),
        )
        value = self.policy.get_value(state_t).item()

        reward = self._compute_step_reward(env)

        act = decode_ppo_action(action, env)
        self.buffer.add(state, action, log_prob.item(), reward, False, value)
        return act

    def _compute_step_reward(self, env) -> float:
        """Compute a dense per-step reward based on HP difference."""
        current = env.current_piece
        if current is None:
            return 0.0
        team = current.team
        hp_self = sum(
            p.health for p in env.action_queue
            if p.team == team and p.is_alive
        )
        hp_enemy = sum(
            p.health for p in env.action_queue
            if p.team != team and p.is_alive
        )
        return (hp_self - hp_enemy) / 300.0  # normalise by max total HP

    def finalise_episode(self, result: int):
        """Apply terminal reward to all steps in the buffer.

        :param result: 1 = P1 win, 2 = P2 win, 0 = draw, -1 = error
        """
        terminal = 1.0 if result == 1 else -1.0 if result == 2 else 0.0

        # Discount the terminal reward back through all steps
        for i in reversed(range(len(self.buffer))):
            self.buffer.rewards[i] += terminal * (self.gamma ** (len(self.buffer) - 1 - i))

        # Mark all steps as terminal (end of episode)
        self.buffer.dones = [True] * len(self.buffer)

    def get_buffer(self) -> RolloutBuffer:
        return self.buffer

    def clear(self):
        self.buffer.clear()


def make_init_strategy() -> Callable:
    """Return the standard sniper init strategy (STR 29, bow + heavy)."""
    from env import InitGameMessage
    from strategies._utils import allocate_init_positions
    from utils import PieceArg, Point

    def init_fn(init_message: InitGameMessage) -> List["PieceArg"]:
        board = init_message.board
        pid = init_message.id
        if pid == 1:
            order = [
                (x, y)
                for y in range(5, 0, -1)
                for x in range(2, board.width - 2)
            ]
        else:
            order = [
                (x, y)
                for y in range(board.height - 6, board.height)
                for x in range(board.width - 3, 2, -1)
            ]
        positions = allocate_init_positions(board, pid, init_message.piece_cnt, order)
        piece_args = []
        for pos in positions:
            arg = PieceArg()
            arg.strength = 29
            arg.dexterity = 1
            arg.intelligence = 0
            arg.equip = Point(3, 3)
            arg.pos = pos
            piece_args.append(arg)
        return piece_args

    return init_fn


def get_opponent_strategy(name: str) -> Tuple[Callable, Callable]:
    """Get init and action strategy for a named opponent."""
    if name == "sniper":
        from strategies.sniper import (
            get_sniper_action_strategy,
            get_sniper_init_strategy,
        )
        return get_sniper_init_strategy(), get_sniper_action_strategy()
    elif name == "sniper_tactical":
        from strategies.sniper_tactical import (
            get_sniper_tactical_action_strategy,
            get_sniper_tactical_init_strategy,
        )
        return get_sniper_tactical_init_strategy(), get_sniper_tactical_action_strategy()
    else:
        raise ValueError(f"Unknown opponent: {name}")


#
# Benchmark evaluation
#


def evaluate(
    policy: PPOPolicy,
    opponent: str,
    n_games: int,
    boards: List[str],
    max_rounds: int = 100,
) -> float:
    """Evaluate win rate against a fixed opponent.

    :returns: Win rate (0.0 to 1.0).
    """
    from benchmark.runner import run_single_game

    p1_init = make_init_strategy()
    logger = PPOTrajectoryLogger(policy)
    p2_init, p2_action = get_opponent_strategy(opponent)

    wins = 0
    for g in range(n_games):
        board = boards[g % len(boards)]
        # Wrap PPO as the action strategy
        p1_action = lambda env, log=logger: log.action_strategy(env)

        import random as _random
        _random.seed(g * 7 + 13)

        import contextlib
        from env import Environment
        env = Environment(local_mode=True, if_log=0)
        env.max_rounds = max_rounds
        env.input_manager.set_function_input_method(1, p1_init, p1_action)
        env.input_manager.set_function_input_method(2, p2_init, p2_action)

        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull):
                env.run(board)

        p1_alive = any(p.is_alive for p in env.player1.pieces)
        p2_alive = any(p.is_alive for p in env.player2.pieces)

        if p1_alive and not p2_alive:
            wins += 1

        logger.clear()

    return wins / n_games


#
# Parallel game collection
#


def _worker_collect(
    policy_state: dict,
    seed: int,
    n_games: int,
    boards: List[str],
    opponent: str,
    gamma: float,
    use_selfplay: bool,
    selfplay_state: dict,
) -> dict:
    """Play games in a subprocess and return trajectory data.

    :param policy_state: Serialized policy state_dict.
    :param seed: Random seed for reproducibility.
    :param n_games: Number of games to play.
    :param boards: Board file paths.
    :param opponent: Opponent name (ignored if use_selfplay).
    :param gamma: Discount factor.
    :param use_selfplay: If True, play against selfplay_state policy.
    :param selfplay_state: Serialized self-play opponent state_dict.
    :returns: Dict with lists of states, actions, log_probs, rewards,
        values, dones.
    """
    import random as _random

    from ml.action_decoder_ppo import decode_ppo_action
    from ml.ppo import PPOPolicy
    from ml.state_encoder import encode_state

    device = torch.device("cpu")
    policy = PPOPolicy().to(device)
    policy.load_state_dict(policy_state)
    policy.eval()

    # Load opponent
    if use_selfplay and selfplay_state:
        opp_policy = PPOPolicy().to(device)
        opp_policy.load_state_dict(selfplay_state)
        opp_policy.eval()

        def opp_action(env):
            s = encode_state(env)
            a, _, _ = opp_policy.sample_action(s, deterministic=True)
            return decode_ppo_action(a, env)

        opp_init = make_init_strategy()
    else:
        opp_init, opp_action = get_opponent_strategy(opponent)

    from collections import defaultdict
    from env import Environment
    import contextlib

    result = defaultdict(list)

    for g in range(n_games):
        board = boards[g % len(boards)]
        _random.seed(seed + g)

        env = Environment(local_mode=True, if_log=0)
        env.max_rounds = 60

        logger = PPOTrajectoryLogger(policy, gamma=gamma)
        p1_init = make_init_strategy()
        env.input_manager.set_function_input_method(
            1, p1_init,
            lambda e, log=logger: log.action_strategy(e),
        )
        env.input_manager.set_function_input_method(2, opp_init, opp_action)

        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull):
                env.run(board)

        p1_alive = any(p.is_alive for p in env.player1.pieces)
        p2_alive = any(p.is_alive for p in env.player2.pieces)
        if p1_alive and not p2_alive:
            result_val = 1
        elif p2_alive and not p1_alive:
            result_val = 2
        else:
            result_val = 0

        logger.finalise_episode(result_val)
        buf = logger.get_buffer()

        result["states"].extend(buf.states)
        result["actions"].extend(buf.actions)
        result["log_probs"].extend(buf.log_probs)
        result["rewards"].extend(buf.rewards)
        result["values"].extend(buf.values)
        result["dones"].extend(buf.dones)

        logger.clear()

    return dict(result)


#
# Main training loop
#


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PPO training for THUAI9")
    parser.add_argument("--epochs", type=int, default=500, help="Training epochs")
    parser.add_argument("--games", type=int, default=64, help="Games per epoch")
    parser.add_argument("--opponent", type=str, default="sniper", help="Opponent strategy")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    parser.add_argument(
        "--board-dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "BoardCase"),
        help="Board directory"
    )
    parser.add_argument("--eval-games", type=int, default=30, help="Evaluation games")
    parser.add_argument("--save-every", type=int, default=10, help="Save checkpoint interval")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--pretrain", type=int, default=100,
        help="BC pretraining steps from sniper demos (default: 100)",
    )
    parser.add_argument(
        "--pretrain-games", type=int, default=64,
        help="Games to collect demos for BC pretraining",
    )
    parser.add_argument(
        "--self-play", action="store_true",
        help="Enable self-play (play against best previous checkpoint)",
    )
    parser.add_argument(
        "--self-play-delay", type=int, default=30,
        help="Epochs before switching to self-play (default: 30)",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Parallel workers for game collection (default: 1). "
             "Use 0 for all CPUs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(WEIGHTS_DIR, exist_ok=True)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    boards = sorted(glob.glob(os.path.join(args.board_dir, "*.txt")))
    if not boards:
        boards = [os.path.join(args.board_dir, "case1.txt")]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    policy = PPOPolicy().to(device)
    optimizer = torch.optim.Adam(policy.parameters(), lr=args.lr, eps=1e-5)

    best_wr = 0.0
    t_start = time.time()

    print(f"PPO Training — {sum(p.numel() for p in policy.parameters())} params")
    print(f"Device: {device}, Board: {boards[0]}")
    print(f"Epochs: {args.epochs}, Games/epoch: {args.games}, Opponent: {args.opponent}")

    #
    # Behavior cloning pretraining
    #
    if args.pretrain > 0:
        print(f"Collecting {args.pretrain_games} demos for {args.pretrain} BC steps ...")
        bc_states: List[np.ndarray] = []
        bc_actions: List[np.ndarray] = []

        class BCLogger:
            def __call__(self, env):
                from strategies._utils import calculate_distance as _cd
                state = encode_state(env)
                p1, p2 = get_opponent_strategy(args.opponent)
                act = p2(env)
                bc_states.append(state)
                enemies = [
                    p for p in env.action_queue
                    if p.team != env.current_piece.team and p.is_alive
                ] if env.current_piece else []
                if env.current_piece and enemies:
                    enemies.sort(key=lambda e: _cd(env.current_piece.position, e.position))

                move_a = 1  # default stay
                target_a = 0
                attack_a = 1 if act.attack else 0
                if act.move and enemies:
                    move_a = 0  # advance
                bc_actions.append(np.array([move_a, target_a, attack_a, 0], dtype=np.int64))
                return act

        for g in range(args.pretrain_games):
            import random as _random
            _random.seed(g * 7 + 42)
            p1_init = make_init_strategy()
            bc_log = BCLogger()
            p2_init = get_opponent_strategy(args.opponent)[0]

            import contextlib
            from env import Environment
            env = Environment(local_mode=True, if_log=0)
            env.max_rounds = 60
            env.input_manager.set_function_input_method(1, p1_init, bc_log)
            env.input_manager.set_function_input_method(2, p2_init, get_opponent_strategy(args.opponent)[1])

            with open(os.devnull, "w") as devnull:
                with contextlib.redirect_stdout(devnull):
                    env.run(boards[g % len(boards)])

        print(f"  Collected {len(bc_states)} state-action pairs")

        # Supervised training
        X = torch.FloatTensor(np.array(bc_states)).to(device)
        y = torch.LongTensor(np.array(bc_actions)).to(device)
        dataset = torch.utils.data.TensorDataset(X, y)
        loader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)

        bc_optimizer = torch.optim.Adam(policy.parameters(), lr=1e-3)
        for step in range(args.pretrain):
            for batch_X, batch_y in loader:
                log_probs, entropy, _ = policy.evaluate_actions(batch_X, batch_y)
                loss = -log_probs.mean()  # maximize log prob of demo actions
                bc_optimizer.zero_grad()
                loss.backward()
                bc_optimizer.step()
            if step % 10 == 0:
                print(f"  BC step {step}: loss={loss.item():.4f} ent={entropy.item():.3f}")

        print("  BC pretraining done. Starting PPO fine-tuning.\n")

    print()

    selfplay_opponent = None

    for epoch in range(args.epochs):
        # --- Determine opponent: fixed or self-play ---
        if (
            args.self_play
            and epoch >= args.self_play_delay
            and selfplay_opponent is not None
        ):
            use_selfplay = True

            def opp_action(env):
                state = encode_state(env)
                a, _, _ = selfplay_opponent.sample_action(state, deterministic=True)
                return decode_ppo_action(a, env)
        else:
            use_selfplay = False
            p2_init, opp_action = get_opponent_strategy(args.opponent)

        # --- Collect trajectories (parallel or sequential) ---
        t0 = time.time()
        n_workers = max(1, args.workers if args.workers > 0 else os.cpu_count() or 4)

        if n_workers > 1:
            import concurrent.futures

            games_per_worker = max(1, args.games // n_workers)
            extra = args.games % n_workers

            policy_state = policy.state_dict()  # serializable state dict
            sp_state = selfplay_opponent.state_dict() if selfplay_opponent else None

            futures = []
            with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as pool:
                offset = 0
                for w in range(n_workers):
                    nw = games_per_worker + (1 if w < extra else 0)
                    fut = pool.submit(
                        _worker_collect,
                        policy_state,
                        args.seed + epoch * 10000 + offset,
                        nw, boards, args.opponent, args.gamma,
                        use_selfplay, sp_state,
                    )
                    futures.append(fut)
                    offset += nw

            buffer = RolloutBuffer()
            for fut in concurrent.futures.as_completed(futures):
                try:
                    data = fut.result()
                    buffer.states.extend(data["states"])
                    buffer.actions.extend(data["actions"])
                    buffer.log_probs.extend(data["log_probs"])
                    buffer.rewards.extend(data["rewards"])
                    buffer.values.extend(data["values"])
                    buffer.dones.extend(data["dones"])
                except Exception as e:
                    print(f"  [worker] failed: {e}", flush=True)
        else:
            # Sequential (original path)
            logger = PPOTrajectoryLogger(policy, gamma=args.gamma)
            p1_init = make_init_strategy()

            for g in range(args.games):
                board = boards[g % len(boards)]
                import random as _random
                _random.seed(args.seed + epoch * 1000 + g)

                import contextlib
                from env import Environment
                env = Environment(local_mode=True, if_log=0)
                env.max_rounds = 60
                env.input_manager.set_function_input_method(
                    1, p1_init,
                    lambda e, log=logger: log.action_strategy(e),
                )
                if use_selfplay:
                    env.input_manager.set_function_input_method(
                        2, make_init_strategy(), opp_action,
                    )
                else:
                    env.input_manager.set_function_input_method(
                        2, p2_init, opp_action,
                    )

                with open(os.devnull, "w") as devnull:
                    with contextlib.redirect_stdout(devnull):
                        env.run(board)

                p1_alive = any(p.is_alive for p in env.player1.pieces)
                p2_alive = any(p.is_alive for p in env.player2.pieces)

                if p1_alive and not p2_alive:
                    result = 1
                elif p2_alive and not p1_alive:
                    result = 2
                else:
                    result = 0

                logger.finalise_episode(result)

            buffer = logger.get_buffer()

        dt_collect = time.time() - t0

        # --- PPO update ---
        t0 = time.time()
        stats = update_policy(policy, optimizer, buffer,
                              gamma=args.gamma)
        dt_update = time.time() - t0

        # --- Evaluate ---
        if epoch % args.save_every == 0:
            eval_opponent = "self" if (use_selfplay and selfplay_opponent is not None) else args.opponent
            t0 = time.time()
            wr = evaluate(policy, args.opponent, args.eval_games, boards)
            dt_eval = time.time() - t0

            total = time.time() - t_start
            print(
                f"Epoch {epoch:3d}: "
                f"wr={wr:.1%} "
                f"pl={stats['policy_loss']:.3f} "
                f"vl={stats['value_loss']:.3f} "
                f"ent={stats['entropy']:.3f} "
                f"len={len(buffer)} "
                f"opp={'self' if use_selfplay else 'fixed'} "
                f"col={dt_collect:.0f}s "
                f"upd={dt_update:.0f}s "
                f"eval={dt_eval:.0f}s "
                f"total={total:.0f}s"
            )

            if wr > best_wr:
                best_wr = wr
                path = os.path.join(WEIGHTS_DIR, f"ppo_epoch{epoch:03d}.pt")
                torch.save(policy.state_dict(), path)
                torch.save(policy.state_dict(),
                           os.path.join(WEIGHTS_DIR, "ppo_latest.pt"))
                print(f"  → New best: {path} ({best_wr:.1%})")

                # Update self-play opponent
                selfplay_opponent = PPOPolicy().to(device)
                selfplay_opponent.load_state_dict(
                    torch.load(os.path.join(WEIGHTS_DIR, "ppo_latest.pt"),
                               map_location=device),
                )

    print(f"\nDone. Best win rate: {best_wr:.1%}")
    if best_wr > 0:
        print(f"Weights saved to {WEIGHTS_DIR}/ppo_latest.pt")


if __name__ == "__main__":
    main()
