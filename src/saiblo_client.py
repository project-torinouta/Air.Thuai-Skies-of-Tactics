# Copyright 2026 saiblo platform <https://saiblo.net>
#
# This SDK copy is distributed from https://api.saiblo.net/api/games/56/download/,
# All rights reserved by saiblo platform. All I modified is translating the
# comment and document string from Chinese to English

"""Saiblo stdin/stdout communication protocol client.

Aligns with the Saiblo platform protocol:

- judger -> AI: **No encapsulation** (no 4-byte length header). This
  implementation reads one message per line of UTF-8 (readline). The body
  is the raw content forwarded by the judger. Blank lines are skipped,
  EOF returns None.
- AI -> judger: **4+n** (4-byte big-endian length + JSON body).
"""

import json
import struct
import sys


class SaibloClient:
    """Client for the Saiblo stdin/stdout communication protocol."""

    @staticmethod
    def read_payload() -> str | None:
        """Read one content payload from the judger.

        The judger sends UTF-8 text without a length header, using newline
        as the message delimiter.

        :returns: The payload string, or None if the stream is closed.
        :rtype: Optional[str]
        """
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            text = line.decode("utf-8").rstrip("\r\n")
            if text:
                return text

    @staticmethod
    def read_message() -> dict | None:
        """Read and deserialize one JSON message from the judger.

        :returns: The parsed JSON dict, or None if the stream is closed.
        :rtype: Optional[dict]
        """
        raw = SaibloClient.read_payload()
        if raw is None:
            return None
        return json.loads(raw)

    @staticmethod
    def write_message(data: dict) -> None:
        """Serialize a dict to JSON and write it to stdout with a 4-byte
        big-endian length header.

        :param data: The data to serialize and send.
        :type data: dict
        """
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        header = struct.pack(">I", len(content))
        sys.stdout.buffer.write(header + content)
        sys.stdout.buffer.flush()
