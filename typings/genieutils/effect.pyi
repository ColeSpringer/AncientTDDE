class EffectCommand:
    type: int
    a: int
    b: int
    c: int
    d: float

class Effect:
    name: str
    effect_commands: list[EffectCommand]
