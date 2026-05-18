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

"""Download match replays from the Saiblo API.

Usage:
    python get_replays.py                                    # uses defaults (limit=40, offset=0)
    python get_replays.py --username player1                 # fetch matches for a specific player
    python get_replays.py --limit 100 --offset 20            # pagination
    python get_replays.py --output-dir ./my_replays          # custom output directory
    python get_replays.py --token "$SAIBLO_TOKEN"            # provide token inline
    python get_replays.py --token "$SAIBLO_TOKEN" --username player1 --limit 10
"""

import argparse
import os

import requests

BASE = "https://api.saiblo.net"
API_URL = "https://api.saiblo.net/api/matches/"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download match replays from the Saiblo API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python get_replays.py\n"
            "  python get_replays.py --username player1 --limit 10\n"
            "  python get_replays.py --token $SAIBLO_TOKEN\n"
        ),
    )
    parser.add_argument(
        "--username",
        type=str,
        default="ashgrey",
        help="Filter matches by username (default: ashgrey)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Number of matches per page (default: 40)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Pagination offset (default: 0)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="replay",
        help="Directory to save replay files (default: replay/)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help=(
            "Saiblo API token. Falls back to SAIBLO_TOKEN env var "
            "if not provided."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    token = args.token or os.environ.get("SAIBLO_TOKEN")
    if not token:
        print("Error: no token provided. Use --token or set SAIBLO_TOKEN.")
        return

    params = {
        "limit": str(args.limit),
        "offset": str(args.offset),
        "username": args.username,
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

    os.makedirs(args.output_dir, exist_ok=True)

    try:
        response = requests.get(API_URL, headers=headers, params=params)
        response.raise_for_status()
        matches_data = response.json()

        for res in matches_data["results"]:
            players = res["info"]
            competitor = ""

            if res["state"] != "评测成功" :
                # There are other possible states, we only check the succeeded game play
                continue

            for player in players:
                if player["user"]["username"] != "ashgrey" :
                    if competitor != "":
                        competitor += "-" + player["user"]["username"]
                    else:
                        competitor = player["user"]["username"]

            replay_id = res["id"]
            download_url = BASE + res["url"]

            replay = requests.get(download_url, headers=headers, stream=True)

            filepath = os.path.join(
                args.output_dir, f"{competitor}-{replay_id}.json"
            )
            with open(filepath, "wb") as f:
                for chunk in replay.iter_content(chunk_size=8192):
                    f.write(chunk)
                print(f"→ Saving replay to {f.name}")

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"An error occurred: {err}")


if __name__ == "__main__":
    main()
