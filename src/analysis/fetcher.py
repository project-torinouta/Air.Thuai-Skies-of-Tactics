"""Download match replays from the Saiblo API."""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

import requests


API_BASE = "https://api.saiblo.net"
MATCHES_URL = f"{API_BASE}/api/matches/"


def fetch_match_list(
    username: str,
    token: str,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """Fetch the list of matches for a given username.

    :param username: Saiblo username.
    :type username: str
    :param token: Saiblo API token.
    :type token: str
    :param limit: Max matches to fetch (default: 50).
    :type limit: int
    :param offset: Pagination offset (default: 0).
    :type offset: int
    :returns: List of match result dicts.
    :rtype: List[Dict]
    :raises requests.HTTPError: If the API request fails.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
    }
    params = {"limit": str(limit), "offset": str(offset), "username": username}
    resp = requests.get(MATCHES_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def download_replay(
    match_data: Dict,
    token: str,
    output_dir: str,
) -> Optional[Tuple[str, int]]:
    """Download a single replay JSON and save to disk.

    :param match_data: Match dict from ``fetch_match_list``.
    :type match_data: Dict
    :param token: Saiblo API token.
    :type token: str
    :param output_dir: Directory to save the replay file.
    :type output_dir: str
    :returns: ``(opponent_name, match_id)`` or None if skipped.
    :rtype: Optional[Tuple[str, int]]
    """
    state = match_data.get("state", "")
    if state != "评测成功":
        return None

    players = match_data.get("info", [])
    opponent = ""
    for player in players:
        uname = player.get("user", {}).get("username", "")
        if uname != "ashgrey":
            if opponent:
                opponent += "-" + uname
            else:
                opponent = uname

    if not opponent:
        return None

    match_id = match_data["id"]
    download_url = API_BASE + match_data["url"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
    }
    resp = requests.get(download_url, headers=headers, timeout=30)
    resp.raise_for_status()

    os.makedirs(output_dir, exist_ok=True)
    fpath = os.path.join(output_dir, f"{opponent}-{match_id}.json")
    with open(fpath, "w") as f:
        json.dump(resp.json(), f, indent=2)

    return opponent, match_id


def load_local_replays(replay_dir: str) -> List[Tuple[str, int, dict]]:
    """Load all replay JSONs from a local directory.

    Files are expected to be named ``{opponent}-{match_id}.json``.

    :param replay_dir: Directory containing replay files.
    :type replay_dir: str
    :returns: List of ``(opponent, match_id, data)`` tuples.
    :rtype: List[Tuple[str, int, dict]]
    """
    results: List[Tuple[str, int, dict]] = []
    pattern = re.compile(r"(\w+)-(\d+)\.json")

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
