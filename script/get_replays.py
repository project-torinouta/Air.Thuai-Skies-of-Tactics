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

import requests
import os

base = "https://api.saiblo.net"
url = "https://api.saiblo.net/api/matches/"

# Query parameters unpacked for easy pagination adjustments
params = {
    "limit": "40",
    "offset": "0",
    "username": "ashgrey"
}

headers = {
    "Authorization": f"Bearer {os.environ.get("SAIBLO_TOKEN")}",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Origin": "https://www.saiblo.net",
    "Referer": "https://www.saiblo.net/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0"
}

def main() -> None :
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Throws an error for bad status codes (4xx, 5xx)

        # Parse and print the JSON matching structure
        matches_data = response.json()

        for res in matches_data["results"] :
            players = res["info"]
            competitor = ""

            for player in players :
                # The two players, we want the competitor's name
                if player["user"]["username"] != params["username"] :
                    competitor = player["user"]["username"]

            replay_id = res["id"]
            download_url_segment = res["url"]
            download_url = base + download_url_segment

            replay = requests.get(download_url, headers=headers, stream=True)

            with open(f"replay/{competitor}-{replay_id}.json", "wb") as f :
                for chunk in replay.iter_content(chunk_size=8192) :
                    f.write(chunk)
                print(f"→ Saving replay to {f.name}")

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"An error occurred: {err}")

if __name__ == "__main__" :
    main()
