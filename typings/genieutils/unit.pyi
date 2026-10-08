class ResourceStorage:
    type: int
    amount: float
    flag: int

class ResourceCost:
    type: int
    amount: int
    flag: int

class TrainLocation:
    train_time: int
    unit_id: int

class AttackOrArmor:
    class_: int
    amount: int

class Type50:
    attacks: list[AttackOrArmor]
    armours: list[AttackOrArmor]
    max_range: float
    min_range: float
    reload_time: float
    accuracy_percent: int

class Creatable:
    resource_costs: tuple[ResourceCost, ResourceCost, ResourceCost]
    train_locations: list[TrainLocation]
    total_projectiles: float
    max_total_projectiles: int

class Bird:
    work_rate: float

class Unit:
    id: int
    name: str
    class_: int
    hit_points: int
    line_of_sight: float
    speed: float | None
    resource_storages: tuple[ResourceStorage, ResourceStorage, ResourceStorage]
    type_50: Type50 | None
    creatable: Creatable | None
    bird: Bird | None
