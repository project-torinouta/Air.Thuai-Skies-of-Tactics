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

import argparse
import os
import json

import requests

API_BASE_URL = "https://api.saiblo.net"
USER_URL = "https://api.saiblo.net/api/matches"
RANK_LIST_URL = "https://api.saiblo.net/api/games/56/ladders"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the initial strategy of players in rank list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python get_rank_initial_strategy.py\n"
            "  python get_rank_initial_strategy.py --token $SAIBLO_TOKEN\n"
        )
    )
    parser.add_argument(
        "--token",
        type=str,
        help="Saiblo API token. Falls back to SAIBLO_TOKEN env var if not provided"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of matches per page (default: 40)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Pagination offset (default: 0)",
    )
    return parser.parse_args()


# [derived from src/analysis/parser.py]
def get_initial_property(
    player_name: str,
    token: str,
    rank: int
) -> str:
    """Download a single replay JSON and save to disk.

    :param player_name: Analyzed player's username.
    :type player_name: str
    :param token: Saiblo API token.
    :type token: str
    :returns: The presentation of player's initial property
    :rtype: str
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Origin": "https://www.saiblo.net",
        "Referer": "https://www.saiblo.net/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) "
            "Gecko/20100101 Firefox/150.0"
        ),
    }
    rerun = True
    offset = 0
    limit = 20
    try:
        while rerun:
            params = {
                "username": player_name,
                "limit": limit,
                "offset": offset
            }
            response = requests.get(f"{USER_URL}", headers=headers, params=params)
            response.raise_for_status()
            player_camp = ""
            data = response.json()
            for idx, match in enumerate(data["results"]):
                if match["state"] != "评测成功":
                    if idx == len(data["results"]) - 1:
                        offset += limit
                        rerun = True
                    continue
                else:
                    rerun = False
                first_player_name = match["info"][0]["user"]["username"]
                if first_player_name == player_name:
                    player_camp = "Red"
                else:
                    player_camp = "Blue"

                download_url = API_BASE_URL + match["url"]
                download_headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json, text/plain, */*",
                }
                resp = requests.get(download_url, headers=download_headers, timeout=3000)
                resp.raise_for_status()

                replay = resp.json()
                strength = 0
                intelligence = 0
                dexterity = 0

                table = []
                count = 0
                for soldiers in replay["soldiersData"]:
                    if soldiers["camp"] == player_camp:
                        strength = int(soldiers["stats"]["strength"])
                        intelligence = int(soldiers["stats"]["intelligence"])
                        # we assume that all users add up to 30 property points
                        dexterity = 30 - strength - intelligence

                        table.append("{:<6} {:<20} {:<12} {:<20} {:<12}".format(
                            f"#{rank}",
                            player_name + f" p{count + 1}",
                            strength,
                            intelligence,
                            dexterity
                        ))
                        count += 1
                return "\n".join(table)

    except requests.HTTPError as e:
        return ""
    except KeyError as e:
        return ""


def main() -> None:
    args = parse_args()

    token = args.token or os.environ.get("SAIBLO_TOKEN")
    if not token:
        print("Error: no token provided. Use --token or set SAIBLO_TOKEN.")
        return

    params = {
        "offset": str(args.offset),
        "limit": str(args.limit)
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Origin": "https://www.saiblo.net",
        "Referer": "https://www.saiblo.net/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) "
            "Gecko/20100101 Firefox/150.0"
        ),
    }

    try:
        response = requests.get(RANK_LIST_URL, params=params, headers=headers)
        response.raise_for_status()
        matches_data = response.json()

        rank = 1
        table = []
        table.append("{:<6} {:<20} {:<12} {:<20} {:<12}".format(
            "rank",
            "user",
            "strength",
            "intelligence",
            "dexterity"
        ))
        table.append("=" * 74)
        for player in matches_data["results"]:
            username = player["user"]
            score = player["score"]
            init = get_initial_property(username, token, rank)
            if init != "":
                table.append(init)
            rank += 1

        print("\n".join(table))
    except requests.HTTPError as e:
        print("Something error happened during connecting to rank url")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
