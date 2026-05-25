"""Game execution — run single games and matchups."""

import contextlib
import os
import random
import sys
from typing import Callable, List, Optional, Tuple

from env import Environment

from benchmark import StrategyPair
from benchmark.models import GameResult, MatchupSeries


def run_single_game(
    board_file: str,
    p1_strategy: StrategyPair,
    p2_strategy: StrategyPair,
    max_rounds: int = 100,
    verbose: bool = False,
    round_callback: "Optional[Callable[[Environment, int], None]]" = None,
    suppress_stdout: bool = True,
) -> GameResult:
    """Run a single game between two strategy pairs and return the result.

    :param board_file: Path to the board definition file.
    :type board_file: str
    :param p1_strategy: (init, action) for player 1.
    :type p1_strategy: StrategyPair
    :param p2_strategy: (init, action) for player 2.
    :type p2_strategy: StrategyPair
    :param max_rounds: Maximum rounds before the game is stopped.
    :type max_rounds: int
    :param verbose: Whether to show game output.
    :type verbose: bool
    :param round_callback: Optional callback ``(env, round_number)`` called
        after each round.  Used by the heuristic loop to capture snapshots.
    :type round_callback: Optional[Callable]
    :returns: A GameResult with result, rounds, first_blood, survivors.
    :rtype: GameResult
    """
    env = Environment(local_mode=True, if_log=0)
    env.max_rounds = max_rounds

    p1_init, p1_action = p1_strategy
    p2_init, p2_action = p2_strategy

    env.input_manager.set_function_input_method(1, p1_init, p1_action)
    env.input_manager.set_function_input_method(2, p2_init, p2_action)

    try:
        if suppress_stdout:
            with open(os.devnull, "w") as _hl_sink:
                with contextlib.redirect_stdout(_hl_sink):
                    env.initialize(board_file)
                    while not env.is_game_over:
                        env.step()
                        if round_callback is not None:
                            round_callback(env, env.round_number)
        else:
            env.initialize(board_file)
            if verbose:
                env.visualize_board()
            while not env.is_game_over:
                env.step()
                if verbose:
                    env.visualize_board()
                if round_callback is not None:
                    round_callback(env, env.round_number)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return GameResult(result=-1, rounds=0)

    rounds = env.round_number

    p1_alive = any(p.is_alive for p in env.player1.pieces)
    p2_alive = any(p.is_alive for p in env.player2.pieces)

    if p1_alive and not p2_alive:
        result = 1
    elif p2_alive and not p1_alive:
        result = 2
    else:
        result = 0

    # First blood: earliest death_round across all pieces
    first_blood = -1
    for piece in list(env.player1.pieces) + list(env.player2.pieces):
        dr = getattr(piece, "death_round", -1)
        if dr > 0 and (first_blood < 0 or dr < first_blood):
            first_blood = dr

    survivors_p1 = sum(1 for p in env.player1.pieces if p.is_alive)
    survivors_p2 = sum(1 for p in env.player2.pieces if p.is_alive)

    return GameResult(
        result=result,
        rounds=rounds,
        first_blood=first_blood,
        survivors_p1=survivors_p1,
        survivors_p2=survivors_p2,
    )


def run_matchup(
    board_files: List[str],
    p1_pair: StrategyPair,
    p2_pair: StrategyPair,
    rounds: int,
    max_rounds: int,
) -> Tuple[int, int, int]:
    """Run multiple games between two strategy pairs and return aggregates.

    :param board_files: List of available board file paths.
    :type board_files: List[str]
    :param p1_pair: (init, action) for player 1.
    :type p1_pair: StrategyPair
    :param p2_pair: (init, action) for player 2.
    :type p2_pair: StrategyPair
    :param rounds: Number of games to play.
    :type rounds: int
    :param max_rounds: Max game rounds before timeout.
    :type max_rounds: int
    :returns: (p1_wins, p2_wins, draws) counts.
    :rtype: Tuple[int, int, int]
    """
    p1_wins = 0
    p2_wins = 0
    draws = 0

    for _ in range(rounds):
        board = random.choice(board_files)
        gr = run_single_game(board, p1_pair, p2_pair, max_rounds)
        if gr.result == 1:
            p1_wins += 1
        elif gr.result == 2:
            p2_wins += 1
        elif gr.result == 0:
            draws += 1

        sys.stdout.write(".")
        sys.stdout.flush()

    return p1_wins, p2_wins, draws


def run_matchup_series(
    board_files: List[str],
    p1_pair: StrategyPair,
    p2_pair: StrategyPair,
    rounds: int,
    max_rounds: int,
) -> MatchupSeries:
    """Run multiple games and return detailed per-game data.

    :param board_files: List of available board file paths.
    :type board_files: List[str]
    :param p1_pair: (init, action) for player 1.
    :type p1_pair: StrategyPair
    :param p2_pair: (init, action) for player 2.
    :type p2_pair: StrategyPair
    :param rounds: Number of games to play.
    :type rounds: int
    :param max_rounds: Max game rounds before timeout.
    :type max_rounds: int
    :returns: A MatchupSeries with per-game results, lengths, etc.
    :rtype: MatchupSeries
    """
    series = MatchupSeries()
    for i in range(rounds):
        board = random.choice(board_files)
        gr = run_single_game(board, p1_pair, p2_pair, max_rounds)
        series.results.append(gr.result)
        series.lengths.append(gr.rounds)
        series.first_bloods.append(gr.first_blood)
        series.survivors.append((gr.survivors_p1, gr.survivors_p2))
        sys.stdout.write(f"\r  {i + 1}/{rounds}")
        sys.stdout.flush()
    return series
