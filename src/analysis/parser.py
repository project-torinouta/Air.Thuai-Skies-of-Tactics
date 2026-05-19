"""Parse raw Saiblo replay JSON into structured data models."""

from typing import Dict, List, Tuple

from analysis.models import ParsedReplay, RoundAction, RoundSnapshot, SoldierInit


def parse_replay(data: dict, match_id: int, opponent: str) -> ParsedReplay:
    """Parse a raw replay JSON dict into a ``ParsedReplay``.

    :param data: Raw JSON decoded from the replay file.
    :type data: dict
    :param match_id: Saiblo match ID.
    :type match_id: int
    :param opponent: Opponent username.
    :type opponent: str
    :returns: Structured replay data.
    :rtype: ParsedReplay
    """
    map_data = data.get("mapdata", {})
    map_width = map_data.get("mapWidth", 20)
    soldiers_raw = data.get("soldiersData", [])
    rounds_raw = data.get("gameRounds", [])

    # --- Parse initial soldier configs ---
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

    # --- Parse round snapshots and actions ---
    round_snapshots: List[RoundSnapshot] = []
    all_actions: List[RoundAction] = []

    for rnd in rounds_raw:
        rn = rnd.get("roundNumber", 0)

        # Parse actions in this round
        for act in rnd.get("actions", []):
            at = act.get("actionType", "")
            sid = act.get("soldierId", -1)

            path: List[Tuple[int, int]] = []
            if at == "Movement":
                raw_path = act.get("path", [])
                path = [(p.get("x", 0), p.get("z", 0)) for p in raw_path]

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

        # Parse round-end snapshot
        positions: Dict[int, Tuple[int, int]] = {}
        hp: Dict[int, int] = {}
        for stat in rnd.get("stats", []):
            sid = stat.get("soldierId", -1)
            stats_block = stat.get("Stats", stat)
            pos = stat.get("position", {})
            positions[sid] = (pos.get("x", 0), pos.get("z", 0))
            hp[sid] = stats_block.get("health", 0)

        round_snapshots.append(RoundSnapshot(
            round_number=rn,
            positions=positions,
            hp=hp,
            is_end=rnd.get("end") == "true",
        ))

    # --- Determine winner ---
    winner = _determine_winner(soldiers, round_snapshots)

    # --- Determine ashgrey's camp ---
    # ashgrey uses STR 29 → 108 HP (sniper build)
    # If both sides have the same HP/build, default to Red
    ashgrey_camp = _guess_ashgrey_camp(soldiers)

    return ParsedReplay(
        match_id=match_id,
        opponent=opponent,
        map_width=map_width,
        soldiers=soldiers,
        rounds=round_snapshots,
        actions=all_actions,
        winner=winner,
        ashgrey_camp=ashgrey_camp,
    )


def _determine_winner(
    soldiers: List[SoldierInit],
    snapshots: List[RoundSnapshot],
) -> str:
    """Determine the winning camp from final-round snapshot."""
    if not snapshots:
        return "Draw"
    last = snapshots[-1]
    if not last.hp:
        return "Draw"

    alive_camps: Dict[str, int] = {}
    soldier_camp: Dict[int, str] = {s.id: s.camp for s in soldiers}
    for sid in last.hp:
        camp = soldier_camp.get(sid, "")
        alive_camps[camp] = alive_camps.get(camp, 0) + 1

    if len(alive_camps) == 1:
        return list(alive_camps.keys())[0]
    return "Draw"


def _guess_ashgrey_camp(soldiers: List[SoldierInit]) -> str:
    """Guess which camp ashgrey played based on the STR 29 build.

    ashgrey's sniper uses STR 29 → health = 50 + 29*2 = 108.
    If both camps have the same build, default to the low-z (top) side = Red.
    """
    camp_hp: Dict[str, List[int]] = {}
    for s in soldiers:
        camp_hp.setdefault(s.camp, []).append(s.health)

    # Look for 108 HP which indicates STR 29 (ashgrey's build)
    ashgrey_found = None
    for camp, hps in camp_hp.items():
        if all(h == 108 for h in hps):
            ashgrey_found = camp
            break

    if ashgrey_found:
        other = [c for c in camp_hp if c != ashgrey_found][0]
        if all(h != 108 for h in camp_hp[other]):
            return ashgrey_found

    # Fallback: camp with lower average z = Red
    camp_z: Dict[str, List[int]] = {}
    for s in soldiers:
        camp_z.setdefault(s.camp, []).append(s.z)
    if not camp_z:
        return "Red"
    avg_z = {c: sum(zs) / len(zs) for c, zs in camp_z.items()}
    return min(avg_z, key=lambda c: avg_z[c])  # lower z = Red
