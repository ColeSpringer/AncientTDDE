from enum import IntEnum

class VictoryCondition(IntEnum):
    STANDARD = 0
    CONQUEST = 1
    SCORE = 2
    TIME_LIMIT = 3
    CUSTOM = 4
    SECONDARY_GAME_MODE = 6
