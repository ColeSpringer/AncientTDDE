// Progress lives in scenario variables. These arrays are only reusable query buffers and
// the shop's previous King sample, which a reload simply starts again.
int ancientUnitArray = -1;
int ancientRelicArray = -1;
int ancientVillagerArray = -1;
int ancientPadCounts = -1;
int ancientLeakCounts = -1;
int ancientSpawnArray = -1;
int ancientKingIds = -1;
int ancientKingX = -1;
int ancientKingY = -1;
int ancientKingStill = -1;
int ancientKingSampled = -1;
int ancientKingPads = -1;
int ancientSampleX = -1;
int ancientSampleY = -1;
int ancientSampleStill = -1;
int ancientLastNotice = -1;

int laneVariable(int player = 1, int field = 0) {
    return (cLaneBase + (player - 1) * cLaneStride + field);
}

int laneValue(int player = 1, int field = 0) {
    return (xsTriggerVariable(laneVariable(player, field)));
}

void laneSet(int player = 1, int field = 0, int value = 0) {
    xsSetTriggerVariable(laneVariable(player, field), value);
}

string ancientDigit(int digit = 0) {
    if (digit == 1) return ("1");
    if (digit == 2) return ("2");
    if (digit == 3) return ("3");
    if (digit == 4) return ("4");
    if (digit == 5) return ("5");
    if (digit == 6) return ("6");
    if (digit == 7) return ("7");
    if (digit == 8) return ("8");
    if (digit == 9) return ("9");
    return ("0");
}

// Messages join text only, so numbers are written out digit by digit.
string ancientText(int value = 0) {
    int rest = value;
    if (rest < 0) rest = 0 - rest;
    string text = ancientDigit(rest % 10);
    rest = rest / 10;
    while (rest > 0) {
        text = ancientDigit(rest % 10) + text;
        rest = rest / 10;
    }
    if (value < 0) text = "-" + text;
    return (text);
}

string ancientPlayer(int player = 1) {
    return ("P" + ancientText(player));
}

string ancientCount(int count = 0, string single = "", string plural = "") {
    if (count == 1) return ("1 " + single);
    return (ancientText(count) + " " + plural);
}

// Does the lane own the once-only purchase with this ownership mask? Repeatable ones have none.
bool ancientOwns(int player = 1, int mask = 0) {
    if (mask <= 0) return (false);
    return ((laneValue(player, fOwned) / mask) % 2 == 1);
}

// Ask the lane's native message trigger to tell its player something. The trigger clears the
// field once shown, so a second message in the same second waits for its next cause.
void ancientMessage(int player = 1, int code = 0) {
    if (laneValue(player, fMessage) == 0) laneSet(player, fMessage, code);
}

// The life Outpost's hit points show the share of lives left; the objectives show the number.
void ancientShowLives(int player = 1) {
    int lives = laneValue(player, fLives);
    if (lives < 0) lives = 0;
    float hitpoints = xsGetObjectAttribute(player, cLifeObject, cHitpoints) * lives / cLives;
    if (hitpoints < 1.0) hitpoints = 1.0;
    xsSetUnitHitpoints(laneLife(player), hitpoints);
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

string ancientTowerAccess(int player = 1) {
    string available = "Watch Tower";
    string missing = "";
    for (tower = 0; < cTowerKinds) {
        if (xsGetTechState(towerTech(tower), player) == cTechStateDisabled) {
            if (missing != "") missing = missing + ", ";
            missing = missing + towerName(tower);
        } else {
            available = available + ", " + towerName(tower);
        }
    }
    string text = ancientPlayer(player) + " towers: " + available;
    if (missing != "") text = text + "; unavailable: " + missing;
    return (text);
}

void ancientInitialize() {
    int participants = 0;
    for (player = 1; <= 7) {
        if (xsGetPlayerInGame(player) && (xsGetPlayerType(player) == cPlayerTypeHuman)) {
            laneSet(player, fActive, 1);
            laneSet(player, fLives, cLives);
            ancientShowLives(player);
            participants = participants + 1;
        } else {
            laneSet(player, fCleanup, 1);
        }
    }
    xsSetTriggerVariable(vParticipants, participants);
    xsSetTriggerVariable(vSurvivors, participants);
    xsSetTriggerVariable(vPhase, sSetup);
    xsSetTriggerVariable(vRemaining, cSetup);
    xsSetTriggerVariable(vCountdown, cSetup + cPreparation);
    xsSetTriggerVariable(vDisplayWave, 1);
    xsSetTriggerVariable(vWave, -1);
    xsChatData("Ancient TD: human defense lanes = %d", participants);
}

// Collect every lane's losses before changing state or selecting a winner.
int ancientCollect() {
    if (ancientLeakCounts < 0) ancientLeakCounts = xsArrayCreateInt(8, 0, "ancientLeakCounts");
    for (slot = 1; <= 7) {
        laneSet(slot, fCount, 0);
        xsArraySetInt(ancientLeakCounts, slot, 0);
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
                            xsArraySetInt(ancientLeakCounts, defender, xsArrayGetInt(ancientLeakCounts, defender) + 1);
                            xsRemoveUnit(unit);
                        } else {
                            laneSet(defender, fCount, laneValue(defender, fCount) + 1);
                        }
                    }
                }
            }
        }
    }
    for (leaker = 1; <= 7) {
        int leaks = xsArrayGetInt(ancientLeakCounts, leaker);
        if (leaks > 0) {
            int left = laneValue(leaker, fLives);
            if (left < 0) left = 0;
            string lost = ancientPlayer(leaker) + " lost " + ancientCount(leaks, "life", "lives");
            xsChatData(lost + "; " + ancientText(left) + " left.");
            ancientShowLives(leaker);
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
                laneSet(player, fPurchase, 0);
                laneSet(player, fKings, 0);
                laneSet(player, fAttack, 0);
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
    xsSetTriggerVariable(vCountdown, 0);
    for (slot = 1; <= 7) {
        laneSet(slot, fSpawn, 0);
    }
}

void ancientStartWave() {
    int wave = xsTriggerVariable(vWave) + 1;
    xsSetTriggerVariable(vWave, wave);
    xsSetTriggerVariable(vDisplayWave, wave + 1);
    xsSetTriggerVariable(vCountdown, waveDuration(wave));
    xsSetTriggerVariable(vElapsed, 0);
    xsSetTriggerVariable(vBatches, 0);
    xsSetTriggerVariable(vSpawnClock, 0);
    if (waveBoss(wave) == 1) xsSetTriggerVariable(vPhase, sBoss);
    else xsSetTriggerVariable(vPhase, sWave);
    string number = ancientText(wave + 1) + " of " + ancientText(cWaveCount);
    xsChatData("Wave " + number + ": " + waveName(wave) + ".");
}

void ancientWaveCleared(int wave = 0) {
    if (cWaveKings <= 0) return;
    for (payee = 1; <= 7) {
        if (laneValue(payee, fActive) == 1) laneSet(payee, fKings, laneValue(payee, fKings) + cWaveKings);
    }
    string reward = ancientCount(cWaveKings, "King", "Kings");
    xsChatData("Wave " + ancientText(wave + 1) + " cleared: " + reward + " for every surviving lane.");
}

// The pad a position lies on, or 0.
int ancientPadAt(float x = 0.0, float y = 0.0) {
    for (pad = 1; <= cShopCount) {
        if ((x >= shopX1(pad)) && (x < shopX2(pad) + 1) && (y >= shopY1(pad)) && (y < shopY2(pad) + 1)) return (pad);
    }
    return (0);
}

bool ancientRelicsWaiting(int player = 1) {
    ancientRelicArray = xsGetPlayerUnitIds(0, cRelic, ancientRelicArray);
    for (index = 0; < xsArrayGetSize(ancientRelicArray)) {
        int relic = xsArrayGetInt(ancientRelicArray, index);
        if (xsGetGarrisonedInUnitId(relic) < 0) {
            vector position = xsGetUnitPosition(relic);
            float x = xsVectorGetX(position);
            float y = xsVectorGetY(position);
            if ((x >= laneRelicX1(player)) && (x < laneRelicX2(player) + 1) && (y >= laneRelicY1(player)) && (y < laneRelicY2(player) + 1)) return (true);
        }
    }
    return (false);
}

// The message explaining why a purchase cannot be made now, or 0 when it can.
int ancientRefusal(int player = 1, int purchase = 0) {
    if (ancientOwns(player, shopMask(purchase))) return (cMessageOwned);
    int needed = shopRequires(purchase);
    if ((needed > 0) && (ancientOwns(player, shopMask(needed)) == false)) return (cMessageRequires);
    if ((purchase == cRelicsPurchase) && ancientRelicsWaiting(player)) return (cMessageRelics);
    if ((shopTech(purchase) > 0) && (xsGetTechState(shopTech(purchase), player) == cTechStateDisabled)) return (cMessageCivilization);
    return (0);
}

// Explain a refusal once, again after a pause, and at once when the refusal changes.
void ancientNotice(int player = 1, int purchase = 0, int code = 0) {
    if (ancientLastNotice < 0) ancientLastNotice = xsArrayCreateInt(8, 0, "ancientLastNotice");
    int key = purchase * 16 + code;
    if ((laneValue(player, fNotice) > 0) && (xsArrayGetInt(ancientLastNotice, player) == key)) return;
    if (laneValue(player, fMessage) != 0) return;
    laneSet(player, fMessage, code);
    laneSet(player, fNotice, cNoticeSeconds);
    xsArraySetInt(ancientLastNotice, player, key);
}

// How many consecutive samples this King has stayed within half a tile of where it was.
int ancientKingStillness(int player = 1, int king = -1, float x = 0.0, float y = 0.0) {
    int base = player * cKingSlots;
    for (slot = 0; < xsArrayGetInt(ancientKingSampled, player)) {
        if (xsArrayGetInt(ancientKingIds, base + slot) == king) {
            float dx = x - xsArrayGetFloat(ancientKingX, base + slot);
            float dy = y - xsArrayGetFloat(ancientKingY, base + slot);
            if ((dx * dx + dy * dy) < 0.25) return (xsArrayGetInt(ancientKingStill, base + slot) + 1);
            return (0);
        }
    }
    return (0);
}

// Count the Kings standing on each pad. Walking Kings move over a tile between samples, so a
// King counts only once it has stood still for cStillSamples whole samples.
void ancientSampleKings(int player = 1) {
    if (ancientKingIds < 0) {
        ancientKingIds = xsArrayCreateInt(8 * cKingSlots, -1, "ancientKingIds");
        ancientKingX = xsArrayCreateFloat(8 * cKingSlots, 0.0, "ancientKingX");
        ancientKingY = xsArrayCreateFloat(8 * cKingSlots, 0.0, "ancientKingY");
        ancientKingStill = xsArrayCreateInt(8 * cKingSlots, 0, "ancientKingStill");
        ancientKingSampled = xsArrayCreateInt(8, 0, "ancientKingSampled");
        ancientKingPads = xsArrayCreateInt(cKingSlots, 0, "ancientKingPads");
        ancientSampleX = xsArrayCreateFloat(cKingSlots, 0.0, "ancientSampleX");
        ancientSampleY = xsArrayCreateFloat(cKingSlots, 0.0, "ancientSampleY");
        ancientSampleStill = xsArrayCreateInt(cKingSlots, 0, "ancientSampleStill");
        ancientPadCounts = xsArrayCreateInt(cShopCount + 1, 0, "ancientPadCounts");
    }
    for (pad = 0; <= cShopCount) {
        xsArraySetInt(ancientPadCounts, pad, 0);
    }
    ancientUnitArray = xsGetPlayerUnitIds(player, cKing, ancientUnitArray);
    int kings = xsArrayGetSize(ancientUnitArray);
    if (kings > cKingSlots) kings = cKingSlots;
    for (index = 0; < kings) {
        int king = xsArrayGetInt(ancientUnitArray, index);
        vector position = xsGetUnitPosition(king);
        float x = xsVectorGetX(position);
        float y = xsVectorGetY(position);
        int still = ancientKingStillness(player, king, x, y);
        int standing = 0;
        if ((still >= cStillSamples) && (xsGetUnitHitpoints(king) > 0) && (xsGetGarrisonedInUnitId(king) < 0)) standing = ancientPadAt(x, y);
        xsArraySetInt(ancientKingPads, index, standing);
        xsArraySetInt(ancientPadCounts, standing, xsArrayGetInt(ancientPadCounts, standing) + 1);
        xsArraySetFloat(ancientSampleX, index, x);
        xsArraySetFloat(ancientSampleY, index, y);
        xsArraySetInt(ancientSampleStill, index, still);
    }
    // This sample replaces the previous one only after every King has been compared with it.
    int base = player * cKingSlots;
    for (record = 0; < kings) {
        xsArraySetInt(ancientKingIds, base + record, xsArrayGetInt(ancientUnitArray, record));
        xsArraySetFloat(ancientKingX, base + record, xsArrayGetFloat(ancientSampleX, record));
        xsArraySetFloat(ancientKingY, base + record, xsArrayGetFloat(ancientSampleY, record));
        xsArraySetInt(ancientKingStill, base + record, xsArrayGetInt(ancientSampleStill, record));
    }
    xsArraySetInt(ancientKingSampled, player, kings);
}

// Create every unit a purchase places, or none: a blocked spot keeps the Kings.
bool ancientSpawn(int player = 1, int purchase = 0) {
    int key = player * cSpawnStride + purchase;
    int first = spawnStart(key);
    int total = spawnCount(key);
    if (ancientSpawnArray < 0) ancientSpawnArray = xsArrayCreateInt(cSpawnSlots, -1, "ancientSpawnArray");
    int made = 0;
    for (entry = 0; < total) {
        if (made == entry) {
            int owner = player;
            if (spawnGaia(first + entry) == 1) owner = 0;
            vector spot = xsVectorSet(0.1 * spawnX10(first + entry), 0.1 * spawnY10(first + entry), 0.0);
            int unit = xsCreateUnit(spawnUnit(first + entry), owner, spot, false, true, true);
            if (unit >= 0) {
                xsArraySetInt(ancientSpawnArray, made, unit);
                made = made + 1;
            }
        }
    }
    if (made == total) return (true);
    for (undo = 0; < made) {
        xsRemoveUnit(xsArrayGetInt(ancientSpawnArray, undo));
    }
    return (false);
}

// One request at a time: a purchase waits until the native triggers have applied the last.
void ancientShop(int player = 1) {
    ancientSampleKings(player);
    if (laneValue(player, fPurchase) != 0) return;
    int ready = 0;
    int refused = 0;
    int reason = 0;
    for (candidate = 1; <= cShopCount) {
        if (xsArrayGetInt(ancientPadCounts, candidate) >= shopPrice(candidate)) {
            int code = ancientRefusal(player, candidate);
            if (code == 0) {
                if (ready == 0) ready = candidate;
            } else if (refused == 0) {
                refused = candidate;
                reason = code;
            }
        }
    }
    if ((ready > 0) && (ancientSpawn(player, ready) == false)) {
        refused = ready;
        reason = cMessageNoRoom;
        ready = 0;
    }
    if (reason > 0) ancientNotice(player, refused, reason);
    if (ready == 0) return;
    int paid = 0;
    int kings = xsArrayGetSize(ancientUnitArray);
    if (kings > cKingSlots) kings = cKingSlots;
    for (payment = 0; < kings) {
        if ((paid < shopPrice(ready)) && (xsArrayGetInt(ancientKingPads, payment) == ready)) {
            xsRemoveUnit(xsArrayGetInt(ancientUnitArray, payment));
            paid = paid + 1;
        }
    }
    if (shopMask(ready) > 0) laneSet(player, fOwned, laneValue(player, fOwned) + shopMask(ready));
    laneSet(player, fPurchase, ready);
}

// Owed Kings appear one per second at the lane's stall once it is clear.
void ancientKings(int player = 1) {
    if (laneValue(player, fKings) <= 0) return;
    vector stall = xsVectorSet(0.1 * laneStallX10(player), 0.1 * laneStallY10(player), 0.0);
    if (xsCreateUnit(cKing, player, stall, false, true, true) >= 0) laneSet(player, fKings, laneValue(player, fKings) - 1);
}

// A villager on a transfer pad reappears, unchanged, in the area the pad leads to once there is room.
void ancientTransfers(int player = 1) {
    ancientVillagerArray = xsGetPlayerUnitIds(player, cVillagerClass, ancientVillagerArray);
    for (index = 0; < xsArrayGetSize(ancientVillagerArray)) {
        int villager = xsArrayGetInt(ancientVillagerArray, index);
        if ((xsGetUnitHitpoints(villager) > 0) && (xsGetGarrisonedInUnitId(villager) < 0)) {
            vector position = xsGetUnitPosition(villager);
            float x = xsVectorGetX(position);
            float y = xsVectorGetY(position);
            int moved = 0;
            for (transfer = 0; < cTransferCount) {
                int slot = player * cTransferCount + transfer;
                if ((moved == 0) && (x >= transferX1(slot)) && (x < transferX2(slot) + 1) && (y >= transferY1(slot)) && (y < transferY2(slot) + 1)) {
                    vector arrival = xsVectorSet(0.1 * transferX10(slot), 0.1 * transferY10(slot), 0.0);
                    if (xsCreateUnit(xsGetUnitType(villager), player, arrival, false, true, true) >= 0) {
                        xsRemoveUnit(villager);
                        moved = 1;
                    }
                }
            }
        }
    }
}

// Age purchases bring their tower upgrade only to civilizations that have it.
void ancientUpgrades(int player = 1) {
    for (upgrade = 1; <= cShopCount) {
        int tech = shopUpgrade(upgrade);
        if ((tech > 0) && ancientOwns(player, shopMask(upgrade))) {
            int state = xsGetTechState(tech, player);
            if ((state != cTechStateDisabled) && (state != cTechStateDone)) xsResearchTechnology(tech, true, false, player);
        }
    }
}

void ancientConvert(int player = 1) {
    float gold = xsPlayerAttribute(player, cAttributeGold);
    int kings = 0;
    while (gold >= cKingGold) {
        gold = gold - cKingGold;
        kings = kings + 1;
    }
    if (kings == 0) return;
    xsSetPlayerAttribute(player, cAttributeGold, gold);
    laneSet(player, fKings, laneValue(player, fKings) + kings);
    ancientMessage(player, cMessageGold);
}

void ancientKillRewards(int player = 1) {
    float kills = xsPlayerAttribute(player, cAttributeKills);
    int paid = laneValue(player, fKills);
    int rewards = 0;
    while ((paid + rewards + 1) * cKillsPerReward <= kills) {
        rewards = rewards + 1;
    }
    if (rewards == 0) return;
    xsSetPlayerAttribute(player, cAttributeStone, xsPlayerAttribute(player, cAttributeStone) + rewards * cKillStone);
    xsSetPlayerAttribute(player, cAttributeWood, xsPlayerAttribute(player, cAttributeWood) + rewards * cKillWood);
    int kings = (paid + rewards) / cRewardsPerKing - paid / cRewardsPerKing;
    laneSet(player, fKills, paid + rewards);
    if (kings > 0) {
        laneSet(player, fKings, laneValue(player, fKings) + kings);
        ancientMessage(player, cMessageKillKing);
    }
}

void ancientInvest(int player = 1, int clock = 0) {
    for (invest = 0; < cInvestCount) {
        if (ancientOwns(player, investMask(invest)) && (clock % investPeriod(invest) == 0)) {
            int pays = investPays(invest);
            int amount = investAmount(invest);
            if (pays == cPaysGold) {
                xsSetPlayerAttribute(player, cAttributeGold, xsPlayerAttribute(player, cAttributeGold) + amount);
            } else if (pays == cPaysStone) {
                xsSetPlayerAttribute(player, cAttributeStone, xsPlayerAttribute(player, cAttributeStone) + amount);
            } else if (pays == cPaysKing) {
                laneSet(player, fKings, laneValue(player, fKings) + amount);
            } else {
                laneSet(player, fAttack, laneValue(player, fAttack) + amount);
            }
        }
    }
}

void ancientRepair(int player = 1, int clock = 0) {
    if (ancientOwns(player, cRepairMask) == false) return;
    if (clock % cRepairInterval != 0) return;
    int lives = laneValue(player, fLives);
    float stone = xsPlayerAttribute(player, cAttributeStone);
    if ((lives >= cLives) || (stone < cRepairStone)) return;
    xsSetPlayerAttribute(player, cAttributeStone, stone - cRepairStone);
    laneSet(player, fLives, lives + 1);
    ancientShowLives(player);
}

void ancientEconomy(int state = 0) {
    int clock = xsTriggerVariable(vEconomy);
    if (state != sSetup) {
        clock = clock + 1;
        xsSetTriggerVariable(vEconomy, clock);
    }
    for (player = 1; <= 7) {
        if ((laneValue(player, fActive) == 1) && (laneValue(player, fInitialized) == 1)) {
            ancientShop(player);
            ancientUpgrades(player);
            ancientTransfers(player);
            ancientConvert(player);
            ancientKillRewards(player);
            if (state != sSetup) {
                ancientInvest(player, clock);
                ancientRepair(player, clock);
            }
            ancientKings(player);
            int notice = laneValue(player, fNotice);
            if (notice > 0) laneSet(player, fNotice, notice - 1);
        }
    }
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
    ancientEconomy(state);
    // Native requests are acknowledged once. Waiting preserves a common wave schedule.
    bool ready = true;
    for (player = 1; <= 7) {
        if ((laneValue(player, fActive) == 1) &&
            ((laneValue(player, fInitialized) == 0) || (laneValue(player, fSpawn) > 0))) ready = false;
    }
    if (ready == false) return;
    if ((state == sSetup) || (state == sPreparation)) {
        int remaining = xsTriggerVariable(vRemaining) - 1;
        xsSetTriggerVariable(vRemaining, remaining);
        if (state == sSetup) xsSetTriggerVariable(vCountdown, remaining + cPreparation);
        else xsSetTriggerVariable(vCountdown, remaining);
        xsSetTriggerVariable(vDisplayWave, xsTriggerVariable(vWave) + 2);
        if (remaining <= 0) {
            if (state == sSetup) {
                xsSetTriggerVariable(vPhase, sPreparation);
                xsSetTriggerVariable(vRemaining, cPreparation);
                xsChatData("Prepare your towers. First wave in %d game seconds.", cPreparation);
                for (newcomer = 1; <= 7) {
                    if (laneValue(newcomer, fActive) == 1) xsChatData(ancientTowerAccess(newcomer));
                }
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
                if (laneValue(survivor, fActive) == 1) {
                    laneSet(survivor, fLives, laneValue(survivor, fLives) - damage);
                    ancientShowLives(survivor);
                }
            }
            xsSetTriggerVariable(vSuddenRound, xsTriggerVariable(vSuddenRound) + 1);
            suddenRemaining = cSuddenInterval;
        }
        xsSetTriggerVariable(vRemaining, suddenRemaining);
        xsSetTriggerVariable(vCountdown, suddenRemaining);
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
    int spawning = waveDuration(wave) - elapsed;
    if (spawning < 0) spawning = 0;
    xsSetTriggerVariable(vCountdown, spawning);
    // The final batch must already have been acknowledged and all enemies resolved.
    if ((elapsed >= waveDuration(wave)) && (batches == waveBatches(wave)) && (alive == 0)) {
        ancientWaveCleared(wave);
        if (wave + 1 < cWaveCount) {
            xsSetTriggerVariable(vPhase, sPreparation);
            xsSetTriggerVariable(vRemaining, cIntermission);
            xsSetTriggerVariable(vCountdown, cIntermission);
            xsSetTriggerVariable(vDisplayWave, wave + 2);
            xsChatData("Next: wave " + ancientText(wave + 2) + ", " + waveName(wave + 1) + ", in " + ancientText(cIntermission) + " game seconds.");
        } else if (xsTriggerVariable(vParticipants) == 1) ancientFinish(true);
        else {
            xsSetTriggerVariable(vPhase, sSuddenDeath);
            xsSetTriggerVariable(vRemaining, cSuddenInterval);
            xsSetTriggerVariable(vCountdown, cSuddenInterval);
            xsChatData("Sudden death: all survivors lose increasing lives every %d seconds.", cSuddenInterval);
        }
    }
}
