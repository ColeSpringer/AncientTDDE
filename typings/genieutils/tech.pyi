class ResearchResourceCost:
    type: int
    amount: int
    flag: int

class ResearchLocation:
    location_id: int
    research_time: int

class Tech:
    required_techs: tuple[int, int, int, int, int, int]
    resource_costs: tuple[ResearchResourceCost, ResearchResourceCost, ResearchResourceCost]
    required_tech_count: int
    civ: int
    effect_id: int
    name: str
    research_locations: list[ResearchLocation]
