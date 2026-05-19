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

"""Parse raw Saiblo replay JSON into structured data models."""

from typing import Dict, List, Tuple

from analysis.models import ParsedReplay, RoundAction, RoundSnapshot, SoldierInit


def parse_replay(
    data: dict,
    match_id: int,
    opponent: str,
    user: str,
    user_camp: str
) -> ParsedReplay:
    """Parse a raw replay JSON dict into a ``ParsedReplay``.

    :param data: Raw JSON decoded from the replay file.
    :type data: dict
    :param match_id: Saiblo match ID.
    :type match_id: int
    :param opponent: Opponent username.
    :type opponent: str
    :param user: The analysis user's username.
    :type user: str
    :param user_camp: The camp of user, it can only be achieved by URL response \
        cannot be parsed from replay file
    :type user_camp: str
    :returns: Structured replay data.
    :rtype: ParsedReplay
    """
    map_data = data.get("mapdata", {})
    map_width = map_data.get("mapWidth", 20)
    soldiers_raw = data.get("soldiersData", [])
    rounds_raw = data.get("gameRounds", [])

    # Parse initial soldier configs, this can be used to copy the initial strategy

    soldiers: List[SoldierInit] = []

    for s in soldiers_raw:
        pos = s.get("position", {})
        stats = s.get("stats", {})

        soldiers.append(SoldierInit(
            id=s["ID"],
            soldier_type=s.get("soldierType", 3),
            camp=s["camp"],
            x=pos.get("x", 0),
            z=pos.get("z", 0),
            strength=stats.get("strength", 0),
            intelligence=stats.get("intelligence", 0),
            health=stats.get("health", 0),
        ))

    # Parse round snapshots and actions, this can be used to analyse user's action

    round_snapshots: List[RoundSnapshot] = []
    all_actions: List[RoundAction] = []

    for rnd in rounds_raw:
        rn = rnd.get("roundNumber", 0)

        # Parse actions in this round, a soldier or a piece can take different
        # actions in one round if it still has action points

        for act in rnd.get("actions", []):
            at = act.get("actionType", "")
            sid = act.get("soldierId", -1)

            path: List[Tuple[int, int]] = []
            if at == "Movement":
                raw_path = act.get("path", [])
                path = [(p.get("x", 0), p.get("z", 0)) for p in raw_path]
                # We only need to know its coordinate on the plane, in y (vertical)
                # action we don't care

            damage = 0
            target_id = -1
            if at == "Attack":
                for dmg_info in act.get("damageDealt", []):
                    target_id = dmg_info.get("targetId", -1)
                    damage += dmg_info.get("damage", 0)

            all_actions.append(RoundAction(
                round_number=rn,
                action_type=at,
                soldier_id=sid,
                target_id=target_id,
                path=path,
                damage=damage,
            ))

        # Parse round-end snapshot states

        positions: Dict[int, Tuple[int, int]] = {}
        elevations: Dict[int, int] = {}
        hp: Dict[int, int] = {}

        for stat in rnd.get("stats", []):
            sid = stat.get("soldierId", -1)
            stats_piece = stat.get("Stats", {})
            # This stat is the property of this piece like health, strength
            # and intelligence

            pos = stat.get("position", {})
            positions[sid] = (pos.get("x", 0), pos.get("z", 0))
            elevations[sid] = pos.get("y", 0)
            hp[sid] = stats_piece.get("health", 0)

        round_snapshots.append(RoundSnapshot(
            round_number=rn,
            positions=positions,
            elevations=elevations,
            hp=hp,
            is_end=rnd.get("end") == "true",
        ))

    winner = _determine_winner(soldiers, round_snapshots)

    # Notice red is first-hand player, blue is second-hand player

    return ParsedReplay(
        match_id=match_id,
        opponent=opponent,
        map_width=map_width,
        soldiers=soldiers,
        rounds=round_snapshots,
        actions=all_actions,
        winner=winner,
        user=user,
        user_camp=user_camp
    )


def _determine_winner(
    soldiers: List[SoldierInit],
    snapshots: List[RoundSnapshot],
) -> str:
    """Determine the winning camp from final-round snapshot."""
    if not snapshots:
        return "Draw"
    last = snapshots[-1]
    if not list(last.hp.values())[0]:
        # It means that everyone is zero hp, if we simply use last.hp then it
        # almost return False
        return "Draw"

    alive_camps: Dict[str, int] = {}
    soldier_camp: Dict[int, str] = {s.id: s.camp for s in soldiers}
    for sid in last.hp:
        camp = soldier_camp.get(sid, "")
        # The last survival soldier's camp
        alive_camps[camp] = alive_camps.get(camp, 0) + 1
        # When there is no camp property, this logic sets the value initial to 1

    if len(alive_camps) == 1:
        return list(alive_camps.keys())[0]
    return "Draw"
