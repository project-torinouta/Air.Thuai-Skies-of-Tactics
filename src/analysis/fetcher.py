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

"""Download match replays from the Saiblo API."""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

import requests


API_BASE = "https://api.saiblo.net"
MATCHES_URL = f"{API_BASE}/api/matches/"


def fetch_all_matches(
    username: str,
    token: str,
    max_games: int = 200,
) -> List[Dict]:
    """Fetch all matches for a user, paginating through offsets.

    :param username: Saiblo username.
    :type username: str
    :param token: Saiblo API token.
    :type token: str
    :param max_games: Maximum games to fetch (default: 200).
    :type max_games: int
    :returns: List of match result dicts.
    :rtype: List[Dict]
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
    }
    all_results: List[Dict] = []
    offset = 0
    limit = 50

    while len(all_results) < max_games:
        try:
            params = {
                "limit": str(limit),
                "offset": str(offset),
                "username": username
            }
            # When the all results if less than our wanted max games we still need
            # to gain complete information, so `offset += limit`

            resp = requests.get(MATCHES_URL, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])

            if not results:
                # When we encounter the last pagination
                break

            all_results.extend(results)
            offset += limit
        except requests.HTTPError as e:
            print(f"Something error happened when requesting for {MATCHES_URL}")

    return all_results[:max_games]


def _extract_player_ai(player: Dict) -> Tuple[str, int]:
    """Extract AI name and version from a player info dict.

    :param player: They player's info
    :type player: Dict
    :returns: `(entity_name, version)` from the `code` block.
    :rtype: Tuple[str, int]
    """
    code = player.get("code", {})
    if isinstance(code, dict):
        return code.get("entity", ""), code.get("version", 0)
        # entity is the name of user's AI
    return "", 0


def _extract_user_info(user: str, players: List[Dict]) -> Tuple[str, str]:
    """Extract user's username and camp from info dict.

    :param user: The username of user
    :type user: str
    :param players: The list of player
    :type players: List[Dict]
    :returns: `(user, user_camp)` from the `info` block.
    :rtype: Tuple[str, str]
    """
    for idx, player in enumerate(players):
        username = player.get("user", {}).get("username", "")
        if username == user:
            if idx == 0:
                return user, "Red"
            elif idx == 1:
                return user, "Blue"


def download_replay(
    match_data: Dict,
    token: str,
    output_dir: str,
    player_name: str
) -> Optional[Tuple[str, int, str, str, int, int]]:
    """Download a single replay JSON and save to disk.

    :param match_data: Match dict from ``fetch_match_list``.
    :type match_data: Dict
    :param token: Saiblo API token.
    :type token: str
    :param output_dir: Directory to save the replay file.
    :type output_dir: str
    :param player_name: Analyzed player's username.
    :type player_name: str
    :returns: ``(my_entity, my_version, opponent_name, opp_entity, opp_version, match_id)``
        or None if skipped.
    :rtype: Optional[Tuple[str, str, int, str, int, int]]
    """
    state = match_data.get("state", "")
    if state != "评测成功":
        return None

    players = match_data.get("info", [])
    # players are two players in one game

    my_entity = ""
    my_version = 0
    opponent = ""
    opp_entity = ""
    opp_version = 0

    for player in players:
        uname = player.get("user", {}).get("username", "")
        if uname == player_name:
            my_entity, my_version = _extract_player_ai(player)
        else:
            if opponent:
                opponent += "-" + uname
            else:
                opponent = uname
                opp_entity, opp_version = _extract_player_ai(player)

    if not opponent:
        return None

    match_id = match_data["id"]
    download_url = API_BASE + match_data["url"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        resp = requests.get(download_url, headers=headers, timeout=30)
        resp.raise_for_status()

        os.makedirs(output_dir, exist_ok=True)
        fpath = os.path.join(output_dir, f"{opponent}-{match_id}.json")
        with open(fpath, "w") as f:
            json.dump(resp.json(), f, indent=2)

        return my_entity, my_version, opponent, opp_entity, opp_version, match_id
    except requests.HTTPError as e:
        print(f"Something error happened when requesting for {download_url}")
        return "", 0, "", "", 0, 0


def load_local_replays(replay_dir: str) -> List[Tuple[str, int, dict]]:
    """Load all replay JSONs from a local directory.

    Files are expected to be named ``{opponent}-{match_id}.json``.

    :param replay_dir: Directory containing replay files.
    :type replay_dir: str
    :returns: List of ``(opponent, match_id, data)`` tuples.
    :rtype: List[Tuple[str, int, dict]]
    """
    results: List[Tuple[str, int, dict]] = []
    pattern = re.compile(r"^(.+)-(\d+)\.json$")

    for fname in sorted(os.listdir(replay_dir)):
        match = pattern.match(fname)
        if not match:
            continue
        opponent = match.group(1)
        match_id = int(match.group(2))
        fpath = os.path.join(replay_dir, fname)
        with open(fpath) as f:
            data = json.load(f)
        results.append((opponent, match_id, data))

    return results
