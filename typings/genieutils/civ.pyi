from genieutils.unit import Unit

class Civ:
    player_type: int
    name: str
    tech_tree_id: int
    team_bonus_id: int
    resources: list[float]
    units: list[Unit | None]
