# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""THUAI9 Python Client - Saiblo stdin/stdout entry point.

Replaces the older gRPC-based client with a direct stdin/stdout
protocol for the Saiblo competition platform.
"""

import argparse
import json
import sys

from env import Environment, InitGameMessage, Player
from json_converter import action_to_dict, env_from_state_json
from saiblo_client import SaibloClient
from strategies.aggressive import (
    get_aggressive_init_strategy,
    get_aggressive_action_strategy,
)
from strategies.defensive import (
    get_defensive_init_strategy,
    get_defensive_action_strategy,
)
from strategies.mcts import get_mcts_action_strategy
from utils import ActionSet

ERROR_MAP = ["RE", "TLE", "OLE"]


def _serialize_piece_args(piece_args):
    """Serialise a list of PieceArg to the format expected by the server.

    Matches the format produced by ``GameEngine._piece_args_from_list``
    on the server side.

    :param piece_args: List of piece arguments to serialise.
    :type piece_args: List[PieceArg]
    :returns: A list of dicts with strength, intelligence, dexterity,
        equip, and pos.
    :rtype: List[dict]
    """
    out = []
    for pa in piece_args:
        out.append(
            {
                "strength": int(pa.strength),
                "intelligence": int(pa.intelligence),
                "dexterity": int(pa.dexterity),
                "equip": {"x": int(pa.equip.x), "y": int(pa.equip.y)},
                "pos": {"x": int(pa.pos.x), "y": int(pa.pos.y)},
            }
        )
    return out


def parse_args() -> argparse.Namespace:
    """Parse Saiblo client command-line arguments.

    :returns: Parsed arguments.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(description="THUAI9 Saiblo Client")
    parser.add_argument(
        "--strategy",
        choices=["aggressive", "defensive", "mcts"],
        default="aggressive",
        help="AI strategy to use (default: aggressive)",
    )
    parser.add_argument(
        "--mcts-simulations",
        type=int,
        default=25,
        help="MCTS simulation count (default: 25)",
    )
    parser.add_argument(
        "--player-id",
        type=int,
        default=-1,
        help="Saiblo seat 0/1; only enforced in local debug, "
        "the server's first-packet seat takes precedence online",
    )
    return parser.parse_args()


def run() -> None:
    """Main game loop for the Saiblo platform.

    Reads JSON messages from stdin (judger), responds with serialised
    action sets to stdout. Handles handshake, state deserialisation,
    strategy invocation, and error reporting.
    """
    args = parse_args()

    if args.strategy == "aggressive":
        action_strategy = get_aggressive_action_strategy()
        init_strategy = get_aggressive_init_strategy()
    elif args.strategy == "defensive":
        action_strategy = get_defensive_action_strategy()
        init_strategy = get_defensive_init_strategy()
    else:
        action_strategy = get_mcts_action_strategy(
            args.mcts_simulations
        )
        init_strategy = get_defensive_init_strategy()

    env = Environment(local_mode=False, if_log=0)
    env.init_board_only()
    player_id = -1
    handshake_done = False

    print("[INFO] Waiting for judger messages...", file=sys.stderr)

    while True:
        raw = SaibloClient.read_payload()
        if raw is None:
            print("[INFO] Connection closed.", file=sys.stderr)
            break

        text = raw.strip()
        if not text:
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse message JSON: {e}", file=sys.stderr)
            continue

        if isinstance(data, dict) and data.get("state") == -1:
            print("[INFO] Game over.", file=sys.stderr)
            break

        if isinstance(data, dict) and data.get("player") == -1:
            try:
                err = json.loads(data.get("content", "{}"))
            except Exception:
                err = {}
            etype = err.get("error", 0)
            label = ERROR_MAP[etype] if etype < len(ERROR_MAP) else "UNKNOWN"
            print(f"[ERROR] AI error: {label}", file=sys.stderr)
            break

        if not handshake_done:
            if isinstance(data, int) and data in (0, 1):
                seat = int(data)
                if args.player_id in (0, 1) and seat != args.player_id:
                    print(
                        f"[WARN] First-round seat {seat} differs from "
                        f"--player-id {args.player_id}; using server value.",
                        file=sys.stderr,
                    )
                player_id = seat
            else:
                print(
                    "[ERROR] First message is not a seat number "
                    "(expected JSON int 0 or 1).",
                    file=sys.stderr,
                )
                break

            handshake_done = True
            init_msg = InitGameMessage()
            init_msg.piece_cnt = Player.PIECE_CNT
            init_msg.id = player_id + 1
            init_msg.board = env.board
            piece_args = init_strategy(init_msg)
            init_body = {
                "phase": "init",
                "pieces": _serialize_piece_args(piece_args),
            }
            SaibloClient.write_message(
                {
                    "player": player_id,
                    "content": json.dumps(init_body, ensure_ascii=False),
                }
            )
            print(
                f"[INFO] Handshake complete, player_id={player_id}, "
                f"deployment sent.",
                file=sys.stderr,
            )
            continue

        if player_id not in (0, 1):
            print("[ERROR] Received state without completing handshake.",
                  file=sys.stderr)
            break

        if not isinstance(data, dict):
            print(
                f"[WARN] Non-dict message ignored: {type(data).__name__}",
                file=sys.stderr,
            )
            continue

        if "currentRound" not in data and "board" not in data:
            print("[WARN] Unrecognised JSON object, ignored.",
                  file=sys.stderr)
            continue

        state_data = data
        cur_team = int(state_data.get("currentPlayerId", 0))
        if cur_team not in (1, 2):
            print("[WARN] Invalid currentPlayerId, skipping.",
                  file=sys.stderr)
            continue

        active_saiblo = cur_team - 1
        if player_id != active_saiblo:
            continue

        env_from_state_json(state_data, env)

        if env.current_piece is None:
            print("[WARN] current_piece is None; sending empty action.",
                  file=sys.stderr)
            empty = {
                "player": player_id,
                "content": json.dumps(
                    {"move": False, "attack": False, "spell": False}
                ),
            }
            SaibloClient.write_message(empty)
            continue

        try:
            action = action_strategy(env)
        except Exception as e:
            print(f"[ERROR] Strategy execution failed: {e}",
                  file=sys.stderr)
            action = ActionSet()

        csharp_pid = player_id + 1
        action_dict = action_to_dict(action, csharp_pid)
        response = {
            "player": player_id,
            "content": json.dumps(action_dict, ensure_ascii=False),
        }
        SaibloClient.write_message(response)
        print(
            f"[INFO] Round "
            f"{state_data.get('currentRound', '?')}: action sent.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    run()
