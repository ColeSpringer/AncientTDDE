from enum import IntEnum

class TechnologyState(IntEnum):
    DISABLED = -1
    NOT_READY = 0
    READY = 1
    RESEARCHING = 2
    DONE = 3
    QUEUED = 4
