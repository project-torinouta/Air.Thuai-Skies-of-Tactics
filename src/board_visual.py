# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""Colourised terminal rendering of the game board.

Used by the local client (``Environment.mode == 0``) to display the board
with coloured output via ``colorama``. This module is lazy-loaded by
``env.py`` and is not imported in the Saiblo entry path.
"""

from colorama import Back, Fore, Style, init

init(autoreset=True)


def visualize_board(env) -> None:
    """Render the current board state with colourised terminal output.

    Piece IDs belonging to player 1 are shown in red; player 2 in blue.
    Blocked cells (state == -1) are shown with a black background.
    Walkable cells (state == 1) are shown in green.

    :param env: The game environment. Access ``env.board``,
        ``env.action_queue``, and ``env.board.grid`` for rendering.
    :type env: Environment
    """
    print("\nCurrent board:")
    print("   ", end="")
    for x in range(env.board.width):
        print(f"{x:2d} ", end="")
    print("\n")

    for y in range(env.board.height):
        print(f"{y:2d} ", end="")
        for x in range(env.board.width):
            cell = env.board.grid[x][y]
            if cell.state == 2:
                piece = next(
                    (p for p in env.action_queue if p.id == cell.piece_id), None
                )
                if piece:
                    if piece.team == 1:
                        print(f"{Fore.RED}{piece.id:2d} ", end="")
                    else:
                        print(f"{Fore.BLUE}{piece.id:2d} ", end="")
                else:
                    print("X  ", end="")
            elif cell.state == -1:
                print(f"{Fore.WHITE}{Back.BLACK}## ", end="")
            else:
                print(f"{Fore.GREEN}{cell.state:2d} ", end="")
        print(Style.RESET_ALL)
    print()
