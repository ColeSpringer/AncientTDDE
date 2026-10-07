// Progress lives in scenario variables. This array is only a reusable query buffer.
int ancientUnitArray = -1;

int laneVariable(int player = 1, int field = 0) {
    return (cLaneBase + (player - 1) * cLaneStride + field);
}

int laneValue(int player = 1, int field = 0) {
    return (xsTriggerVariable(laneVariable(player, field)));
}

void laneSet(int player = 1, int field = 0, int value = 0) {
    xsSetTriggerVariable(laneVariable(player, field), value);
}

// Query every documented object class; DE documents no all-objects wildcard.
void ancientCleanupLane(int player = 1, int berryMill = -1) {
    for (objectClass = cArcherClass; < cSentinelEndClass) {
        ancientUnitArray = xsGetPlayerUnitIds(player, objectClass, ancientUnitArray);
        for (index = 0; < xsArrayGetSize(ancientUnitArray)) {
            int unit = xsArrayGetInt(ancientUnitArray, index);
            if (unit != berryMill) xsRemoveUnit(unit);
        }
    }
}

void ancientInitialize() {
    int participants = 0;
    for (player = 1; <= 7) {
        if (xsGetPlayerInGame(player) && (xsGetPlayerType(player) == cPlayerTypeHuman)) {
            laneSet(player, fActive, 1);
            laneSet(player, fLives, cLives);
            participants = participants + 1;
        } else {
            laneSet(player, fCleanup, 1);
        }
    }
    xsSetTriggerVariable(vParticipants, participants);
    xsSetTriggerVariable(vSurvivors, participants);
    xsSetTriggerVariable(vPhase, sSetup);
    xsSetTriggerVariable(vRemaining, cSetup);
    xsSetTriggerVariable(vWave, -1);
    xsChatData("Ancient TD: human defense lanes = %d", participants);
}

// Collect every lane's losses before changing state or selecting a winner.
int ancientCollect() {
    for (slot = 1; <= 7) {
        laneSet(slot, fCount, 0);
    }
    for (kind = 0; < cEnemyTypes) {
        ancientUnitArray = xsGetPlayerUnitIds(8, enemyType(kind), ancientUnitArray);
        for (index = 0; < xsArrayGetSize(ancientUnitArray)) {
            int unit = xsArrayGetInt(ancientUnitArray, index);
            if (xsGetUnitHitpoints(unit) > 0) {
                vector position = xsGetUnitPosition(unit);
                float x = xsVectorGetX(position);
                float y = xsVectorGetY(position);
                for (defender = 1; <= 7) {
                    if ((y >= laneLowY(defender)) && (y < laneHighY(defender) + 1)) {
                        // Units sent to the exit tile stop just short of its west edge,
                        // so its preceding tile, marked by the exit flags, counts as the exit.
                        if (laneValue(defender, fActive) == 0) {
                            xsRemoveUnit(unit);
                        } else if (x >= laneExitX(defender) - 1) {
                            laneSet(defender, fLives, laneValue(defender, fLives) - 1);
                            xsRemoveUnit(unit);
                        } else {
                            laneSet(defender, fCount, laneValue(defender, fCount) + 1);
                        }
                    }
                }
            }
        }
    }
    int losses = 0;
    int survivors = 0;
    for (player = 1; <= 7) {
        if (laneValue(player, fActive) == 1) {
            if ((laneValue(player, fLives) <= 0) || (xsGetPlayerInGame(player) == false)) {
                laneSet(player, fActive, 0);
                laneSet(player, fLives, 0);
                laneSet(player, fSpawn, 0);
                laneSet(player, fIncome, 0);
                laneSet(player, fCleanup, 1);
                xsChatData("Defense lane eliminated: P%d", player);
                losses = losses + 1;
            } else {
                survivors = survivors + 1;
            }
        }
    }
    xsSetTriggerVariable(vSurvivors, survivors);
    return (losses);
}

void ancientFinish(bool victory = false) {
    int winner = 8;
    if (victory) {
        for (player = 1; <= 7) {
            if (laneValue(player, fActive) == 1) winner = player;
        }
        xsSetTriggerVariable(vPhase, sVictory);
        xsChatData("Ancient TD victory: P%d", winner);
    } else {
        xsSetTriggerVariable(vPhase, sDefeat);
        xsChatData("All defense lanes eliminated. No human winner.");
    }
    xsSetTriggerVariable(vWinner, winner);
    for (slot = 1; <= 7) {
        laneSet(slot, fSpawn, 0);
        laneSet(slot, fIncome, 0);
    }
}

void ancientStartWave() {
    int wave = xsTriggerVariable(vWave) + 1;
    xsSetTriggerVariable(vWave, wave);
    xsSetTriggerVariable(vElapsed, 0);
    xsSetTriggerVariable(vBatches, 0);
    xsSetTriggerVariable(vSpawnClock, 0);
    if (waveBoss(wave) == 1) xsSetTriggerVariable(vPhase, sBoss);
    else xsSetTriggerVariable(vPhase, sWave);
    xsChatData("Wave starting: %d", wave + 1);
}

void ancientTick() {
    int state = xsTriggerVariable(vPhase);
    if ((state == sVictory) || (state == sDefeat)) return;
    if (state == sInitialization) {
        ancientInitialize();
        return;
    }
    int losses = ancientCollect();
    if ((losses > 0) && (state != sElimination)) {
        xsSetTriggerVariable(vResumePhase, state);
        xsSetTriggerVariable(vPhase, sElimination);
        return;
    }
    // A full elimination state separates the snapshot from terminal native effects.
    if (state == sElimination) {
        if (losses > 0) return;
        if (xsTriggerVariable(vSurvivors) == 0) ancientFinish(false);
        else if ((xsTriggerVariable(vParticipants) > 1) && (xsTriggerVariable(vSurvivors) == 1)) ancientFinish(true);
        else xsSetTriggerVariable(vPhase, xsTriggerVariable(vResumePhase));
        return;
    }
    if (xsTriggerVariable(vSurvivors) == 0) {
        ancientFinish(false);
        return;
    }
    // Native requests are acknowledged once. Waiting preserves a common wave schedule.
    bool ready = true;
    for (player = 1; <= 7) {
        if ((laneValue(player, fActive) == 1) &&
            ((laneValue(player, fInitialized) == 0) || (laneValue(player, fSpawn) > 0) ||
             (laneValue(player, fIncome) > 0))) ready = false;
    }
    if (ready == false) return;
    int income = xsTriggerVariable(vIncomeClock) + 1;
    if ((state != sSetup) && (income >= cIncomeInterval)) {
        income = 0;
        for (payee = 1; <= 7) {
            if (laneValue(payee, fActive) == 1) laneSet(payee, fIncome, 1);
        }
    }
    xsSetTriggerVariable(vIncomeClock, income);
    if ((state == sSetup) || (state == sPreparation)) {
        int remaining = xsTriggerVariable(vRemaining) - 1;
        xsSetTriggerVariable(vRemaining, remaining);
        if (remaining <= 0) {
            if (state == sSetup) {
                xsSetTriggerVariable(vPhase, sPreparation);
                xsSetTriggerVariable(vRemaining, cPreparation);
                xsChatData("Prepare your towers. First wave in %d game seconds.", cPreparation);
            } else ancientStartWave();
        }
        return;
    }
    if (state == sSuddenDeath) {
        int suddenRemaining = xsTriggerVariable(vRemaining) - 1;
        if (suddenRemaining <= 0) {
            int damage = cSuddenDamage + xsTriggerVariable(vSuddenRound);
            if (damage > 10) damage = 10;
            for (survivor = 1; <= 7) {
                if (laneValue(survivor, fActive) == 1) laneSet(survivor, fLives, laneValue(survivor, fLives) - damage);
            }
            xsSetTriggerVariable(vSuddenRound, xsTriggerVariable(vSuddenRound) + 1);
            suddenRemaining = cSuddenInterval;
        }
        xsSetTriggerVariable(vRemaining, suddenRemaining);
        // Resolve pressure losses as one batch on the next clock event.
        return;
    }
    int wave = xsTriggerVariable(vWave);
    int elapsed = xsTriggerVariable(vElapsed) + 1;
    int batches = xsTriggerVariable(vBatches);
    int cooldown = xsTriggerVariable(vSpawnClock);
    int alive = 0;
    bool capacity = true;
    for (defender = 1; <= 7) {
        if (laneValue(defender, fActive) == 1) {
            int count = laneValue(defender, fCount);
            alive = alive + count;
            if (count + waveCount(wave) > cEnemyCap) capacity = false;
        }
    }
    if ((batches < waveBatches(wave)) && (cooldown <= 0) && capacity) {
        for (slot = 1; <= 7) {
            if (laneValue(slot, fActive) == 1) laneSet(slot, fSpawn, wave + 1);
        }
        xsSetTriggerVariable(vBatches, batches + 1);
        cooldown = waveInterval(wave);
    }
    xsSetTriggerVariable(vSpawnClock, cooldown - 1);
    xsSetTriggerVariable(vElapsed, elapsed);
    // The final batch must already have been acknowledged and all enemies resolved.
    if ((elapsed >= waveDuration(wave)) && (batches == waveBatches(wave)) && (alive == 0)) {
        if (wave + 1 < cWaveCount) {
            xsSetTriggerVariable(vPhase, sPreparation);
            xsSetTriggerVariable(vRemaining, cIntermission);
            xsChatData("Next wave: %d", wave + 2);
        } else if (xsTriggerVariable(vParticipants) == 1) ancientFinish(true);
        else {
            xsSetTriggerVariable(vPhase, sSuddenDeath);
            xsSetTriggerVariable(vRemaining, cSuddenInterval);
            xsChatData("Sudden death: all survivors lose increasing lives every %d seconds.", cSuddenInterval);
        }
    }
}
