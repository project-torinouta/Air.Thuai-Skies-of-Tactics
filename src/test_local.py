# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""Basic test for the local game functionality."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from env import Environment


def test_local_game() -> bool:
    """Run a basic smoke test of the game environment.

    Creates an environment, initialises it, and verifies that players,
    board, and action queue are populated correctly.

    :returns: True if all checks pass.
    :rtype: bool
    """
    print("=== Local Game Test ===")

    env = Environment(local_mode=True)

    try:
        env.initialize()
        print("[PASS] Game initialised successfully.")

        assert env.player1 is not None, "Player 1 not created."
        assert env.player2 is not None, "Player 2 not created."
        assert env.board is not None, "Board not created."
        assert len(env.action_queue) > 0, "Action queue is empty."

        print("[PASS] Players and board created.")
        print(f"[PASS] Player 1 pieces: {len(env.player1.pieces)}")
        print(f"[PASS] Player 2 pieces: {len(env.player2.pieces)}")
        print(f"[PASS] Action queue size: {len(env.action_queue)}")

        first_piece = env.action_queue[0]
        print(
            f"[PASS] First piece: ID={first_piece.id}, "
            f"Team={first_piece.team}"
        )

        return True

    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_local_game()
    if success:
        print("\n=== All tests passed ===")
        print("Run: python local_client.py")
    else:
        print("\n=== Tests failed ===")
