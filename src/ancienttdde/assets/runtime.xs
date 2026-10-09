// Progress lives in scenario variables. These arrays are only reusable query buffers and
// the shop's previous King sample, which a reload simply starts again.
int ancientUnitArray = -1;
int ancientRelicArray = -1;
int ancientVillagerArray = -1;
int ancientPadCounts = -1;
int ancientLeakCounts = -1;
int ancientLaneRows = -1;
int ancientSpawnArray = -1;
int ancientKingIds = -1;
int ancientKingX = -1;
int ancientKingY = -1;
int ancientKingStill = -1;
int ancientKingPad = -1;
int ancientKingSampled = -1;
int ancientSampleX = -1;
int ancientSampleY = -1;
int ancientSampleStill = -1;
int ancientSamplePad = -1;
int ancientLastNotice = -1;
// Each lane's boss as last seen: the hit points its unit was left with, and the quarter of
// its reservoir it was in.
int ancientBossLast = -1;
int ancientBossQuarter = -1;

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

// The whole part of a non-negative attribute, built bit by bit to stay an integer.
int ancientWhole(float value = 0.0) {
    int whole = 0;
    int step = 1048576;
    while (step > 0) {
        if (whole + step <= value) whole = whole + step;
        step = step / 2;
    }
    return (whole);
}

// Kills of the enemy's units alone: rival traders, raiders and siege a lane kills count for
// nothing.
int ancientWaveKills(int player = 1) {
    return (ancientWhole(xsPlayerAttribute(8, cAttributeKillsByPlayer1 + player - 1)));
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

// Clear a computer-filled or eliminated lane. Query the object classes a lane's units belong
// to; DE documents no all-objects wildcard, and class N is addressed as cArcherClass + N.
void ancientCleanupLane(int player = 1) {
    for (kind = 0; < cLaneClasses) {
        ancientUnitArray = xsGetPlayerUnitIds(player, cArcherClass + laneClass(kind), ancientUnitArray);
        for (index = 0; < xsArrayGetSize(ancientUnitArray)) {
            xsRemoveUnit(xsArrayGetInt(ancientUnitArray, index));
        }
    }
    // One unit keeps the slot in the game: the engine defeats a player who owns nothing. It
    // stands on the lane's third siege islet, which no siege uses. A player who has left the
    // game needs none.
    if (xsGetPlayerInGame(player) == false) return;
    int spare = player * cSiegeSlots + 2;
    vector keep = xsVectorSet(0.1 * siegeX10(spare), 0.1 * siegeY10(spare), 0.0);
    if (xsCreateUnit(cKing, player, keep, false, false, false) < 0) {
        xsChatData(ancientPlayer(player) + "'s cleared lane could not keep its slot, so DE may report it defeated.");
    }
}

// What a King costs this lane: the difficulty's price, adjusted by its civilization profile.
int ancientKingPrice(int player = 1) {
    int price = kingGold(xsTriggerVariable(vDifficulty)) * civGoldPercent(xsGetPlayerCivilization(player)) / 100;
    if (price < 1) price = 1;
    return (price);
}

// The lane's civilization line: its name when the content knows it, its profile's adjustments
// and, when they change it, the lane's own King price.
string ancientCivilization(int player = 1) {
    int civilization = xsGetPlayerCivilization(player);
    string line = ancientPlayer(player);
    string name = civName(civilization);
    if (name != "") line = line + " " + name;
    line = line + ": " + civText(civilization);
    if (civGoldPercent(civilization) != 100) line = line + "; a King per " + ancientText(ancientKingPrice(player)) + " gold";
    return (line + ".");
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

// Add pierce attack or armor to a player's object definition, for existing, new and upgraded
// objects. A native Modify Attribute cannot raise a class past 255; a technology-style effect
// can, but its value packs the class with the amount (class * 256 + amount), so the amount
// goes in steps.
void ancientAddPierce(int player = 1, int unit = -1, int attribute = 0, int amount = 0) {
    int left = amount;
    while (left > 0) {
        int step = left;
        if (step > cClassChunk) step = cClassChunk;
        // The value parameter is a float; DE does not promote an int argument.
        float value = 1.0 * (256 * cPierceClass + step);
        xsEffectAmount(cAddAttribute, unit, attribute, value, player);
        left = left - step;
    }
}

// Add pierce attack to every tower definition of a family.
void ancientAddAttack(int player = 1, int family = 0, int amount = 0) {
    for (member = 0; < familyCount(family)) {
        ancientAddPierce(player, familyUnit(familyStart(family) + member), cAttack, amount);
    }
}

// Create every unit a purchase places, or none: a blocked spot keeps the Kings. Spots in the
// shared trade areas are not checked, so no rival unit can hold a purchase back.
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
            int unit = xsCreateUnit(spawnUnit(first + entry), owner, spot, false, true, spawnShared(first + entry) == 0);
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

// A civilization profile's own tower attack, added like any other.
void ancientCivAttack(int player = 1, int civ = 0) {
    for (family = 0; < cFamilies) {
        int amount = civAttack(family, civ);
        if (amount > 0) ancientAddAttack(player, family, amount);
    }
}

// A granted purchase the lane cannot keep goes back on sale.
void ancientUngrant(int player = 1, int purchase = 0, string reason = "") {
    int mask = shopMask(purchase);
    if ((mask > 0) && ancientOwns(player, mask)) laneSet(player, fOwned, laneValue(player, fOwned) - mask);
    xsChatData(ancientPlayer(player) + ": a starting purchase " + reason + " and stays on sale.");
}

// Place the units and add the tower attack of every purchase the lane's civilization holds
// from the start, as a payment would, once the lane's own setup has run. A purchase for
// civilizations with a technology this one lacks, or whose spot is blocked, goes back on sale
// instead.
void ancientGrant(int player = 1, int civ = 0) {
    for (slot = 0; < cGrantSlots) {
        int purchase = civGrant(civ, slot);
        if (purchase > 0) {
            int tech = shopTech(purchase);
            if ((tech > 0) && (xsGetTechState(tech, player) == cTechStateDisabled)) {
                ancientUngrant(player, purchase, "is not for this civilization");
            } else if (ancientSpawn(player, purchase) == false) {
                ancientUngrant(player, purchase, "could not be placed");
            } else if (shopAttack(purchase) > 0) {
                ancientAddAttack(player, shopAttackFamily(purchase), shopAttack(purchase));
            }
        }
    }
}

// The first human lane chooses the run options. Solo runs play the lobby's difficulty;
// competitive games play one fixed level and start with PvP off.
void ancientInitialize() {
    int participants = 0;
    int chooser = 0;
    for (player = 1; <= 7) {
        if (xsGetPlayerInGame(player) && (xsGetPlayerType(player) == cPlayerTypeHuman)) {
            laneSet(player, fActive, 1);
            laneSet(player, fLives, cLives);
            int civilization = xsGetPlayerCivilization(player);
            laneSet(player, fKings, civKings(civilization));
            laneSet(player, fOwned, civOwned(civilization));
            ancientShowLives(player);
            participants = participants + 1;
            if (chooser == 0) chooser = player;
        } else {
            laneSet(player, fCleanup, 1);
        }
    }
    xsSetTriggerVariable(vParticipants, participants);
    xsSetTriggerVariable(vSurvivors, participants);
    xsSetTriggerVariable(vPhase, sSetup);
    xsSetTriggerVariable(vRemaining, cChoice);
    xsSetTriggerVariable(vCountdown, cChoice + cPreparation);
    xsSetTriggerVariable(vDisplayWave, 1);
    xsSetTriggerVariable(vWave, -1);
    xsSetTriggerVariable(vChooser, chooser);
    xsSetTriggerVariable(vMode, cModeStandard);
    int level = cCompetitiveLevel;
    if (participants == 1) {
        int lobby = xsGetDifficulty();
        if ((lobby >= -1) && (lobby <= 4)) level = lobbyLevel(lobby + 1);
    }
    xsSetTriggerVariable(vDifficulty, level);
    xsChatData("Ancient TD: human defense lanes = %d", participants);
    if (participants == 0) return;
    xsChatData("Difficulty: " + difficultyName(level) + ", a King per " + ancientText(kingGold(level)) + " gold.");
    string window = " within " + ancientText(cChoice) + " game seconds";
    if (participants == 1) {
        xsChatData(ancientPlayer(chooser) + ": select Standard, Endless or Practice below the shop" + window + "; Standard is the default.");
    } else {
        xsChatData(ancientPlayer(chooser) + ": PvP is off; select PvP on below the shop" + window + " to put raiders and the siege power-up on sale.");
    }
}

// Preparation follows the chooser's selection, or the end of the choice window.
void ancientBeginPreparation() {
    xsSetTriggerVariable(vPhase, sPreparation);
    xsSetTriggerVariable(vRemaining, cPreparation);
    xsSetTriggerVariable(vCountdown, cPreparation);
    xsChatData("Prepare your towers. First wave in %d game seconds.", cPreparation);
    for (newcomer = 1; <= 7) {
        if (laneValue(newcomer, fActive) == 1) {
            xsChatData(ancientTowerAccess(newcomer));
            xsChatData(ancientCivilization(newcomer));
        }
    }
}

// The schedule position whose enemies and timing a wave uses: endless waves repeat the
// templates in turn.
int ancientTemplate(int wave = 0) {
    if (wave < cWaveCount) return (wave);
    return (endlessTemplate((wave - cWaveCount) % cEndlessTemplates));
}

// Endless enemies grow each time the templates come round again, up to the last level.
int ancientEndlessLevel(int endless = 0) {
    int level = endless / cEndlessTemplates + 1;
    if (level > cEndlessLevels) level = cEndlessLevels;
    return (level);
}

// Every endless wave adds pierce armor, until the next step would pass the limit.
int ancientEndlessArmor(int endless = 0) {
    if (cArmorStep <= 0) return (0);
    int steps = endless + 1;
    if (steps > cArmorLimit / cArmorStep) steps = cArmorLimit / cArmorStep;
    return (steps * cArmorStep);
}

// The hit points a wave's enemies carry: a boss's can exceed the attribute's limit, which the
// native configuration applied, so the rest is set on the unit itself.
int ancientWaveHitPoints(int wave = 0) {
    if (wave < cWaveCount) return (waveHitPoints(xsTriggerVariable(vDifficulty) * cWaveCount + wave));
    int endless = wave - cWaveCount;
    int position = endless % cEndlessTemplates;
    return (endlessHitPoints((xsTriggerVariable(vDifficulty) * cEndlessTemplates + position) * cEndlessLevels + ancientEndlessLevel(endless) - 1));
}

string ancientWaveText(int wave = 0) {
    int pattern = ancientTemplate(wave);
    string armor = "";
    if (wave >= cWaveCount) armor = ", +" + ancientText(ancientEndlessArmor(wave - cWaveCount)) + " pierce armor";
    if (waveBoss(pattern) == 1) return (waveKey(pattern) + ", a boss with " + ancientText(ancientWaveHitPoints(wave)) + " HP");
    return (ancientText(waveEnemies(pattern)) + " " + waveKey(pattern) + ", " + ancientText(ancientWaveHitPoints(wave)) + " HP each" + armor);
}

// Native triggers set the endless enemies' hit points for a new level, clearing the request;
// the wave spawns once they have. The script adds each armor step itself, past the 255 a
// native effect stops at.
void ancientConfigureEndless(int wave = 0) {
    int endless = wave - cWaveCount;
    int level = ancientEndlessLevel(endless);
    if (level > xsTriggerVariable(vEndlessLevel)) {
        xsSetTriggerVariable(vEndlessLevel, level);
        xsSetTriggerVariable(vEndlessRequest, level);
    }
    int armor = xsTriggerVariable(vArmor);
    int target = ancientEndlessArmor(endless);
    while (armor < target) {
        armor = armor + cArmorStep;
        for (enemy = 0; < cEndlessUnits) {
            ancientAddPierce(8, endlessUnit(enemy), cArmor, cArmorStep);
        }
    }
    xsSetTriggerVariable(vArmor, armor);
    xsSetTriggerVariable(vConfigured, ancientTemplate(wave) + 1);
}

// The options become fixed by the chooser's first selection, which announces itself, or
// when the choice window ends, which announces what stands.
void ancientLock(bool chosen = false) {
    if (xsTriggerVariable(vLocked) == 1) return;
    xsSetTriggerVariable(vLocked, 1);
    if (xsTriggerVariable(vParticipants) > 1) {
        if (chosen == false) xsChatData("PvP is off: no raiders or siege in this game.");
    } else {
        xsChatData(modeName(xsTriggerVariable(vMode)) + " run on " + difficultyName(xsTriggerVariable(vDifficulty)) + ".");
    }
}

void ancientChoose(int player = 1, int code = 0) {
    if (player != xsTriggerVariable(vChooser)) {
        ancientMessage(player, cMessageChooserOnly);
        return;
    }
    if (xsTriggerVariable(vLocked) == 1) {
        ancientMessage(player, cMessageOptionsFixed);
        return;
    }
    bool solo = (xsTriggerVariable(vParticipants) == 1);
    if (code <= cControlPractice) {
        int mode = code - cControlStandard;
        if ((solo == false) && (mode != cModeStandard)) {
            ancientMessage(player, cMessageSoloModes);
            return;
        }
        xsSetTriggerVariable(vMode, mode);
        if (solo) xsChatData(ancientPlayer(player) + " chose " + modeName(mode) + ": " + modeText(mode) + ".");
        else xsChatData(ancientPlayer(player) + " chose Standard with PvP off: no raiders or siege in this game.");
    } else {
        if (solo) {
            ancientMessage(player, cMessageNeedsRivals);
            return;
        }
        int pvp = 0;
        if (code == cControlPvpOn) pvp = 1;
        xsSetTriggerVariable(vPvp, pvp);
        if (pvp == 1) xsChatData(ancientPlayer(player) + " switched PvP on: raiders and the siege power-up go on sale when the first wave starts.");
        else xsChatData(ancientPlayer(player) + " chose PvP off: no raiders or siege in this game.");
    }
    // One selection decides: the options are fixed and preparation begins.
    ancientLock(true);
    if (xsTriggerVariable(vPhase) == sSetup) ancientBeginPreparation();
}

void ancientPractice(int player = 1, int code = 0) {
    if (xsTriggerVariable(vMode) != cModePractice) {
        ancientMessage(player, cMessagePracticeOnly);
        return;
    }
    string who = ancientPlayer(player);
    if (code == cControlNextWave) {
        if (xsTriggerVariable(vPhase) != sPreparation) {
            ancientMessage(player, cMessagePracticeWave);
            return;
        }
        xsSetTriggerVariable(vRemaining, 1);
        xsChatData("Practice: " + who + " started the next wave.");
    } else if (code == cControlKings) {
        laneSet(player, fKings, laneValue(player, fKings) + cPracticeKings);
        xsChatData("Practice: " + who + " received " + ancientCount(cPracticeKings, "King", "Kings") + ".");
    } else if (code == cControlResources) {
        xsSetPlayerAttribute(player, cAttributeFood, xsPlayerAttribute(player, cAttributeFood) + cPracticeResources);
        xsSetPlayerAttribute(player, cAttributeWood, xsPlayerAttribute(player, cAttributeWood) + cPracticeResources);
        xsSetPlayerAttribute(player, cAttributeStone, xsPlayerAttribute(player, cAttributeStone) + cPracticeResources);
        xsSetPlayerAttribute(player, cAttributeGold, xsPlayerAttribute(player, cAttributeGold) + cPracticeResources);
        xsChatData("Practice: " + who + " received " + ancientText(cPracticeResources) + " of each resource.");
    } else {
        laneSet(player, fLives, cLives);
        ancientShowLives(player);
        xsChatData("Practice: " + who + " has all lives back.");
    }
    xsSetTriggerVariable(vAssists, xsTriggerVariable(vAssists) + 1);
}

// The lane's native triggers record each new selection of a control; it acts once and is
// cleared here, so holding it, or reloading while it is held, does nothing more.
void ancientControl(int player = 1) {
    int code = laneValue(player, fControl);
    if (code <= 0) return;
    laneSet(player, fControl, 0);
    if (code <= cRunOptions) ancientChoose(player, code);
    else ancientPractice(player, code);
}

void ancientResult() {
    int participants = xsTriggerVariable(vParticipants);
    string text = "Result: ";
    if (participants > 1) text = text + "Competitive game";
    else text = text + modeName(xsTriggerVariable(vMode)) + " run";
    int cleared = xsTriggerVariable(vCleared);
    text = text + " on " + difficultyName(xsTriggerVariable(vDifficulty)) + ": " + ancientCount(cleared, "wave", "waves") + " cleared";
    if (cleared > cWaveCount) text = text + " (" + ancientText(cleared - cWaveCount) + " endless)";
    if (participants == 1) {
        int player = xsTriggerVariable(vChooser);
        int lives = laneValue(player, fLives);
        if (lives < 0) lives = 0;
        int kills = ancientWaveKills(player);
        text = text + ", " + ancientCount(lives, "life", "lives") + " left, " + ancientCount(kills, "kill", "kills");
    }
    text = text + ", " + ancientCount((xsTriggerVariable(vEconomy) + xsTriggerVariable(vSetupElapsed)) / 60, "game minute", "game minutes");
    int assists = xsTriggerVariable(vAssists);
    if (assists > 0) text = text + ", assisted by " + ancientCount(assists, "practice action", "practice actions");
    xsChatData(text + ".");
}

// Only one player holds the siege: a short warning, then trebuchets on every surviving rival's
// islets for a while. A claim made earlier in the same second keeps the holder.
void ancientClaimSiege(int player = 1, int price = 0) {
    xsSetTriggerVariable(vSiegeOwner, player);
    xsSetTriggerVariable(vSiegePhase, 1);
    xsSetTriggerVariable(vSiegeLeft, cSiegeWarning);
    xsSetTriggerVariable(vSiegeDisplay, 1);
    xsChatData(ancientPlayer(player) + " bought the siege power-up for " + ancientCount(price, "King", "Kings") + ": trebuchets reach every rival in " + ancientText(cSiegeWarning) + " game seconds.");
}

int ancientPlaceSiege(int owner = 1) {
    int made = 0;
    for (rival = 1; <= 7) {
        if ((rival != owner) && (laneValue(rival, fActive) == 1)) {
            for (spot = 0; < cSiegeTrebuchets) {
                int key = rival * cSiegeSlots + spot;
                vector place = xsVectorSet(0.1 * siegeX10(key), 0.1 * siegeY10(key), 0.0);
                if (xsCreateUnit(cTrebuchet, owner, place, false, true, true) >= 0) made = made + 1;
            }
        }
    }
    return (made);
}

// Expiry or the holder's elimination removes every trebuchet, packed or not, and starts the
// shared cooldown and the holder's longer one.
void ancientEndSiege(bool eliminated = false) {
    int owner = xsTriggerVariable(vSiegeOwner);
    if (owner == 0) return;
    for (form = 0; < 2) {
        int kind = cTrebuchet;
        if (form == 1) kind = cPackedTrebuchet;
        ancientUnitArray = xsGetPlayerUnitIds(owner, kind, ancientUnitArray);
        for (index = 0; < xsArrayGetSize(ancientUnitArray)) {
            xsRemoveUnit(xsArrayGetInt(ancientUnitArray, index));
        }
    }
    xsSetTriggerVariable(vSiegeOwner, 0);
    xsSetTriggerVariable(vSiegePhase, 0);
    xsSetTriggerVariable(vSiegeLeft, 0);
    xsSetTriggerVariable(vSiegeCooldown, cSiegeSharedCooldown);
    laneSet(owner, fSiegeCooldown, cSiegeBuyerCooldown);
    xsSetTriggerVariable(vSiegeDisplay, 3);
    string ended = ancientPlayer(owner) + "'s siege has ended";
    if (eliminated) ended = ended + " with the lane";
    xsChatData(ended + ". It can be bought again in " + ancientText(cSiegeSharedCooldown) + " game seconds, by " + ancientPlayer(owner) + " in " + ancientText(cSiegeBuyerCooldown) + ".");
}

void ancientSiege() {
    int cooldown = xsTriggerVariable(vSiegeCooldown);
    if (cooldown > 0) {
        xsSetTriggerVariable(vSiegeCooldown, cooldown - 1);
        if (cooldown == 1) xsChatData("The siege power-up can be bought again.");
    }
    for (buyer = 1; <= 7) {
        int wait = laneValue(buyer, fSiegeCooldown);
        if (wait > 0) laneSet(buyer, fSiegeCooldown, wait - 1);
    }
    int owner = xsTriggerVariable(vSiegeOwner);
    if (owner == 0) return;
    int left = xsTriggerVariable(vSiegeLeft) - 1;
    if (left > 0) {
        xsSetTriggerVariable(vSiegeLeft, left);
        return;
    }
    if (xsTriggerVariable(vSiegePhase) == 1) {
        int made = ancientPlaceSiege(owner);
        xsSetTriggerVariable(vSiegePhase, 2);
        xsSetTriggerVariable(vSiegeLeft, cSiegeActive);
        xsSetTriggerVariable(vSiegeDisplay, 2);
        xsChatData(ancientPlayer(owner) + "'s siege is active: " + ancientCount(made, "trebuchet", "trebuchets") + " for " + ancientText(cSiegeActive) + " game seconds.");
        return;
    }
    ancientEndSiege(false);
}

void ancientBossBuffers() {
    if (ancientBossLast < 0) {
        ancientBossLast = xsArrayCreateInt(8, -1, "ancientBossLast");
        ancientBossQuarter = xsArrayCreateInt(8, -1, "ancientBossQuarter");
    }
}

// What a boss took this second leaves its lane's reservoir, and its unit is topped back up to
// the attribute's limit until the reservoir runs lower than that. Its lane's player hears at
// each quarter spent. After a reload the unit's hit points stand in for the last ones seen.
void ancientBossTrack(int player = 1, int unit = -1) {
    ancientBossBuffers();
    int now = ancientWhole(xsGetUnitHitpoints(unit));
    int last = xsArrayGetInt(ancientBossLast, player);
    if (last < 0) last = now;
    int pool = laneValue(player, fBoss);
    if (now < last) pool = pool - (last - now);
    if (pool < now) pool = now;
    laneSet(player, fBoss, pool);
    int target = pool;
    if (target > cHitPointCap) target = cHitPointCap;
    if (now != target) {
        float restored = 1.0 * target;
        xsSetUnitHitpoints(unit, restored);
    }
    xsArraySetInt(ancientBossLast, player, target);
    int total = ancientWaveHitPoints(xsTriggerVariable(vWave));
    if (total <= 0) return;
    int quarter = (4 * pool + total - 1) / total;
    int before = xsArrayGetInt(ancientBossQuarter, player);
    if ((before < 0) || (before > 4)) before = 4;
    if ((quarter < before) && (quarter >= 1) && (quarter <= 3)) {
        if (quarter == 3) ancientMessage(player, cMessageBossThreeQuarters);
        else if (quarter == 2) ancientMessage(player, cMessageBossHalf);
        else ancientMessage(player, cMessageBossQuarter);
    }
    if (quarter < before) xsArraySetInt(ancientBossQuarter, player, quarter);
}

// Collect every lane's losses before changing state or selecting a winner. A second looks at
// the current wave's enemy type and at one slice of the others, those whose index leaves the
// slice as its remainder, so every type is looked at once in cSweepTicks seconds and no second
// looks at them all. Without a slice, every type is looked at.
int ancientCollect(int live = -1, int slice = -1) {
    if (ancientLeakCounts < 0) ancientLeakCounts = xsArrayCreateInt(8, 0, "ancientLeakCounts");
    // Each lane's first row and the row past its last, read once rather than for every enemy.
    if (ancientLaneRows < 0) {
        ancientLaneRows = xsArrayCreateInt(16, 0, "ancientLaneRows");
        for (row = 1; <= 7) {
            xsArraySetInt(ancientLaneRows, 2 * row, laneLowY(row));
            xsArraySetInt(ancientLaneRows, 2 * row + 1, laneHighY(row) + 1);
        }
    }
    for (slot = 1; <= 7) {
        laneSet(slot, fCount, 0);
        xsArraySetInt(ancientLeakCounts, slot, 0);
    }
    for (kind = 0; < cEnemyTypes) {
        if ((slice < 0) || (kind == live) || (kind % cSweepTicks == slice)) {
            ancientUnitArray = xsGetPlayerUnitIds(8, enemyType(kind), ancientUnitArray);
            int lives = enemyLives(kind);
            bool boss = (enemyBoss(kind) == 1);
            for (index = 0; < xsArrayGetSize(ancientUnitArray)) {
                int unit = xsArrayGetInt(ancientUnitArray, index);
                if (xsGetUnitHitpoints(unit) > 0) {
                    vector position = xsGetUnitPosition(unit);
                    float x = xsVectorGetX(position);
                    float y = xsVectorGetY(position);
                    for (defender = 1; <= 7) {
                        if ((y >= xsArrayGetInt(ancientLaneRows, 2 * defender)) && (y < xsArrayGetInt(ancientLaneRows, 2 * defender + 1))) {
                            // Units sent to the exit tile stop just short of its west edge,
                            // so its preceding tile, marked by the exit flags, counts as the exit.
                            if (laneValue(defender, fActive) == 0) {
                                xsRemoveUnit(unit);
                            } else if (x >= laneExitX(defender) - 1) {
                                laneSet(defender, fLives, laneValue(defender, fLives) - lives);
                                xsArraySetInt(ancientLeakCounts, defender, xsArrayGetInt(ancientLeakCounts, defender) + lives);
                                xsRemoveUnit(unit);
                            } else {
                                laneSet(defender, fCount, laneValue(defender, fCount) + 1);
                                if (boss) ancientBossTrack(defender, unit);
                            }
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
                if (xsTriggerVariable(vSiegeOwner) == player) ancientEndSiege(true);
                laneSet(player, fActive, 0);
                laneSet(player, fLives, 0);
                laneSet(player, fSpawn, 0);
                laneSet(player, fPurchase, 0);
                laneSet(player, fKings, 0);
                laneSet(player, fCleanup, 1);
                xsChatData("Defense lane eliminated: P%d", player);
                losses = losses + 1;
            } else {
                survivors = survivors + 1;
            }
        }
    }
    xsSetTriggerVariable(vSurvivors, survivors);
    // The chooser passes to the next lane still playing; a fallen solo lane stays the chooser,
    // so the result reads its own lives and kills.
    int chooser = xsTriggerVariable(vChooser);
    if ((chooser > 0) && (laneValue(chooser, fActive) == 0)) {
        int heir = 0;
        for (candidate = 1; <= 7) {
            if ((heir == 0) && (laneValue(candidate, fActive) == 1)) heir = candidate;
        }
        if (heir > 0) xsSetTriggerVariable(vChooser, heir);
    }
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
    ancientResult();
}

// Waves after the finale: endless ones in a solo Endless run, sudden death in competition.
string ancientExtraWave(bool capital = false) {
    bool sudden = (xsTriggerVariable(vStage) == cStageSudden);
    if (sudden && capital) return ("Sudden death wave");
    if (sudden) return ("sudden death wave");
    if (capital) return ("Endless wave");
    return ("endless wave");
}

void ancientStartWave() {
    int wave = xsTriggerVariable(vWave) + 1;
    int pattern = ancientTemplate(wave);
    xsSetTriggerVariable(vWave, wave);
    xsSetTriggerVariable(vDisplayWave, wave + 1);
    xsSetTriggerVariable(vCountdown, waveDuration(pattern));
    xsSetTriggerVariable(vElapsed, 0);
    xsSetTriggerVariable(vBatches, 0);
    xsSetTriggerVariable(vSpawnClock, 0);
    if (waveBoss(pattern) == 1) xsSetTriggerVariable(vPhase, sBoss);
    else xsSetTriggerVariable(vPhase, sWave);
    // The countdown to this wave ends now, even when practice started it early.
    xsSetTriggerVariable(vWaveDisplay, 2);
    if (wave < cWaveCount) {
        string number = ancientText(wave + 1) + " of " + ancientText(cWaveCount);
        xsChatData("Wave " + number + ": " + ancientWaveText(wave) + ".");
        return;
    }
    ancientConfigureEndless(wave);
    string extra = ancientExtraWave(true) + " " + ancientText(wave - cWaveCount + 1) + " (wave " + ancientText(wave + 1) + ")";
    xsChatData(extra + ": " + ancientWaveText(wave) + ".");
}

// After the finale, a solo Endless run and competitors who all survived it play on.
void ancientNextWave(int wave = 0) {
    int stage = xsTriggerVariable(vStage);
    if ((wave + 1 >= cWaveCount) && (stage == cStageScheduled)) {
        if (xsTriggerVariable(vParticipants) > 1) {
            stage = cStageSudden;
            xsSetTriggerVariable(vDrain, cSuddenInterval);
            xsChatData("Sudden death: the waves keep growing, and every survivor loses lives every " + ancientText(cSuddenInterval) + " game seconds, more each time.");
        } else if (xsTriggerVariable(vMode) == cModeEndless) {
            stage = cStageEndless;
            xsChatData("Endless: the waves keep coming and growing until your lane falls.");
        } else {
            ancientFinish(true);
            return;
        }
        xsSetTriggerVariable(vStage, stage);
    }
    xsSetTriggerVariable(vPhase, sPreparation);
    xsSetTriggerVariable(vRemaining, cIntermission);
    xsSetTriggerVariable(vCountdown, cIntermission);
    xsSetTriggerVariable(vDisplayWave, wave + 2);
    string next = "wave " + ancientText(wave + 2);
    if (stage != cStageScheduled) {
        xsSetTriggerVariable(vWaveDisplay, 1);
        next = ancientExtraWave(false) + " " + ancientText(wave + 2 - cWaveCount) + " (" + next + ")";
    }
    xsChatData("Next: " + next + ", " + ancientWaveText(wave + 1) + ", in " + ancientText(cIntermission) + " game seconds.");
}

// Where an enemy of a batch stands across the lane: a pair one tile above and one below the
// center, as the original placed them, a third in the middle.
int ancientRowOffset(int count = 1, int index = 0) {
    if (count == 2) {
        if (index == 0) return (-1);
        return (1);
    }
    return (index - (count - 1) / 2);
}

// A batch of the wave's enemies for a lane, created silently and without collision checks so
// nothing holds a wave back. The lane's native trigger then sends them down the lane.
// A boss comes alone with the attribute's limit of hit points; the rest waits in the lane's
// reservoir, which its unit draws on as it is hit.
void ancientSpawnBatch(int player = 1, int pattern = 0, int hitpoints = 0) {
    int count = waveCount(pattern);
    int unit = -1;
    for (index = 0; < count) {
        vector spot = xsVectorSet(0.5 + laneSpawnX(player), 0.5 + laneY(player) + ancientRowOffset(count, index), 0.0);
        unit = xsCreateUnit(waveUnit(pattern), 8, spot, false, false, false);
    }
    if ((waveBoss(pattern) == 1) && (unit >= 0)) {
        ancientBossBuffers();
        laneSet(player, fBoss, hitpoints);
        int shown = hitpoints;
        if (shown > cHitPointCap) shown = cHitPointCap;
        float carried = 1.0 * shown;
        xsSetUnitHitpoints(unit, carried);
        xsArraySetInt(ancientBossLast, player, shown);
        xsArraySetInt(ancientBossQuarter, player, 4);
    }
    laneSet(player, fSpawn, 1);
}

// Sudden death costs every survivor lives at each interval, more each time.
void ancientDrain() {
    int left = xsTriggerVariable(vDrain) - 1;
    if (left <= 0) {
        int damage = cSuddenDamage + xsTriggerVariable(vSuddenRound);
        if (damage > 10) damage = 10;
        for (survivor = 1; <= 7) {
            if (laneValue(survivor, fActive) == 1) {
                laneSet(survivor, fLives, laneValue(survivor, fLives) - damage);
                ancientShowLives(survivor);
            }
        }
        xsSetTriggerVariable(vSuddenRound, xsTriggerVariable(vSuddenRound) + 1);
        xsChatData("Sudden death: every survivor loses " + ancientCount(damage, "life", "lives") + ".");
        left = cSuddenInterval;
    }
    xsSetTriggerVariable(vDrain, left);
}

void ancientWaveCleared(int wave = 0) {
    xsSetTriggerVariable(vCleared, xsTriggerVariable(vCleared) + 1);
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

// Raiders and siege are for sale only in a competitive game with PvP on, from its first wave.
bool ancientInteraction() {
    return ((xsTriggerVariable(vPvp) == 1) && (xsTriggerVariable(vWave) >= 0) && (xsTriggerVariable(vParticipants) > 1));
}

int ancientRivals(int player = 1) {
    int rivals = 0;
    for (rival = 1; <= 7) {
        if ((rival != player) && (laneValue(rival, fActive) == 1)) rivals = rivals + 1;
    }
    return (rivals);
}

// Living raiders of a medium, upgraded forms included, against the player's cap.
bool ancientRaidersFull(int player = 1, int medium = 1) {
    int living = 0;
    for (member = 0; < cRaiderLineSize) {
        int unit = raiderLine(medium * cRaiderLineSize + member);
        if (unit > 0) living = living + xsGetObjectCount(player, unit);
    }
    int cap = raiderCap(medium) + civRaiders(medium, xsGetPlayerCivilization(player));
    return (living >= cap);
}

// The siege costs more for every surviving rival it reaches.
int ancientPrice(int player = 1, int purchase = 0) {
    if (purchase == cSiegePurchase) return (shopPrice(purchase) + cSiegeRivalKings * ancientRivals(player));
    return (shopPrice(purchase));
}

// The message explaining why a purchase cannot be made now, or 0 when it can.
int ancientRefusal(int player = 1, int purchase = 0) {
    if (ancientOwns(player, shopMask(purchase))) return (cMessageOwned);
    int needed = shopRequires(purchase);
    if ((needed > 0) && (ancientOwns(player, shopMask(needed)) == false)) return (cMessageRequires);
    if ((purchase == cRelicsPurchase) && ancientRelicsWaiting(player)) return (cMessageRelics);
    if ((shopTech(purchase) > 0) && (xsGetTechState(shopTech(purchase), player) == cTechStateDisabled)) return (cMessageCivilization);
    int medium = shopRaider(purchase);
    if ((medium == 0) && (purchase != cSiegePurchase)) return (0);
    if (ancientInteraction() == false) return (cMessagePvpOff);
    if (ancientRivals(player) == 0) return (cMessageNoRival);
    if (medium > 0) {
        if (ancientRaidersFull(player, medium)) return (cMessageRaiderCap);
        return (0);
    }
    int holder = xsTriggerVariable(vSiegeOwner);
    if (holder == player) return (cMessageSiegeYours);
    if (holder > 0) return (cMessageSiegeHeld);
    if ((xsTriggerVariable(vSiegeCooldown) > 0) || (laneValue(player, fSiegeCooldown) > 0)) return (cMessageSiegeCooldown);
    return (0);
}

// Explain a refusal once, again after a pause, and at once when the refusal changes.
void ancientNotice(int player = 1, int purchase = 0, int code = 0) {
    if (ancientLastNotice < 0) ancientLastNotice = xsArrayCreateInt(8, 0, "ancientLastNotice");
    int key = purchase * 100 + code;
    if ((laneValue(player, fNotice) > 0) && (xsArrayGetInt(ancientLastNotice, player) == key)) return;
    if (laneValue(player, fMessage) != 0) return;
    laneSet(player, fMessage, code);
    laneSet(player, fNotice, cNoticeSeconds);
    xsArraySetInt(ancientLastNotice, player, key);
}

// Where this King was in the lane's previous sample, or -1. A list that has not changed keeps
// each King at its place, so that place is tried first.
int ancientKingSlot(int player = 1, int king = -1, int guess = 0) {
    int base = player * cKingSlots;
    int sampled = xsArrayGetInt(ancientKingSampled, player);
    if ((guess < sampled) && (xsArrayGetInt(ancientKingIds, base + guess) == king)) return (guess);
    for (slot = 0; < sampled) {
        if (xsArrayGetInt(ancientKingIds, base + slot) == king) return (slot);
    }
    return (-1);
}

// Count the Kings standing on each pad. Walking Kings move over a tile between samples, so a
// King counts only once it has stayed within half a tile of where it was for cStillSamples
// whole samples. A King that has not moved at all since it was counted stands on the pad it
// stood on then, so idle Kings cost no pad search.
void ancientSampleKings(int player = 1) {
    if (ancientKingIds < 0) {
        ancientKingIds = xsArrayCreateInt(8 * cKingSlots, -1, "ancientKingIds");
        ancientKingX = xsArrayCreateFloat(8 * cKingSlots, 0.0, "ancientKingX");
        ancientKingY = xsArrayCreateFloat(8 * cKingSlots, 0.0, "ancientKingY");
        ancientKingStill = xsArrayCreateInt(8 * cKingSlots, 0, "ancientKingStill");
        ancientKingPad = xsArrayCreateInt(8 * cKingSlots, 0, "ancientKingPad");
        ancientKingSampled = xsArrayCreateInt(8, 0, "ancientKingSampled");
        ancientSampleX = xsArrayCreateFloat(cKingSlots, 0.0, "ancientSampleX");
        ancientSampleY = xsArrayCreateFloat(cKingSlots, 0.0, "ancientSampleY");
        ancientSampleStill = xsArrayCreateInt(cKingSlots, 0, "ancientSampleStill");
        ancientSamplePad = xsArrayCreateInt(cKingSlots, 0, "ancientSamplePad");
        ancientPadCounts = xsArrayCreateInt(cShopCount + 1, 0, "ancientPadCounts");
    }
    for (pad = 0; <= cShopCount) {
        xsArraySetInt(ancientPadCounts, pad, 0);
    }
    ancientUnitArray = xsGetPlayerUnitIds(player, cKing, ancientUnitArray);
    int kings = xsArrayGetSize(ancientUnitArray);
    if (kings > cKingSlots) kings = cKingSlots;
    int base = player * cKingSlots;
    for (index = 0; < kings) {
        int king = xsArrayGetInt(ancientUnitArray, index);
        vector position = xsGetUnitPosition(king);
        float x = xsVectorGetX(position);
        float y = xsVectorGetY(position);
        int slot = ancientKingSlot(player, king, index);
        int still = 0;
        bool moved = true;
        if (slot >= 0) {
            float dx = x - xsArrayGetFloat(ancientKingX, base + slot);
            float dy = y - xsArrayGetFloat(ancientKingY, base + slot);
            float distance = dx * dx + dy * dy;
            if (distance < 0.25) still = xsArrayGetInt(ancientKingStill, base + slot) + 1;
            moved = (distance > 0.0);
        }
        int standing = 0;
        if ((still >= cStillSamples) && (xsGetUnitHitpoints(king) > 0) && (xsGetGarrisonedInUnitId(king) < 0)) {
            if ((still > cStillSamples) && (moved == false)) standing = xsArrayGetInt(ancientKingPad, base + slot);
            else standing = ancientPadAt(x, y);
        }
        xsArraySetInt(ancientSamplePad, index, standing);
        xsArraySetInt(ancientPadCounts, standing, xsArrayGetInt(ancientPadCounts, standing) + 1);
        xsArraySetFloat(ancientSampleX, index, x);
        xsArraySetFloat(ancientSampleY, index, y);
        xsArraySetInt(ancientSampleStill, index, still);
    }
    // This sample replaces the previous one only after every King has been compared with it.
    for (record = 0; < kings) {
        xsArraySetInt(ancientKingIds, base + record, xsArrayGetInt(ancientUnitArray, record));
        xsArraySetFloat(ancientKingX, base + record, xsArrayGetFloat(ancientSampleX, record));
        xsArraySetFloat(ancientKingY, base + record, xsArrayGetFloat(ancientSampleY, record));
        xsArraySetInt(ancientKingStill, base + record, xsArrayGetInt(ancientSampleStill, record));
        xsArraySetInt(ancientKingPad, base + record, xsArrayGetInt(ancientSamplePad, record));
    }
    xsArraySetInt(ancientKingSampled, player, kings);
}

// One request at a time: a purchase waits until the native triggers have applied the last.
void ancientShop(int player = 1) {
    ancientSampleKings(player);
    if (laneValue(player, fPurchase) != 0) return;
    int ready = 0;
    int refused = 0;
    int reason = 0;
    for (candidate = 1; <= cShopCount) {
        if (xsArrayGetInt(ancientPadCounts, candidate) >= ancientPrice(player, candidate)) {
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
    int price = ancientPrice(player, ready);
    int paid = 0;
    int kings = xsArrayGetSize(ancientUnitArray);
    if (kings > cKingSlots) kings = cKingSlots;
    for (payment = 0; < kings) {
        if ((paid < price) && (xsArrayGetInt(ancientSamplePad, payment) == ready)) {
            xsRemoveUnit(xsArrayGetInt(ancientUnitArray, payment));
            paid = paid + 1;
        }
    }
    if (shopMask(ready) > 0) laneSet(player, fOwned, laneValue(player, fOwned) + shopMask(ready));
    if (shopAttack(ready) > 0) ancientAddAttack(player, shopAttackFamily(ready), shopAttack(ready));
    if (ready == cSiegePurchase) ancientClaimSiege(player, price);
    laneSet(player, fPurchase, ready);
}

// Owed Kings appear one per second at the lane's stall. Every lane's Kings walk the shop, so
// the stall is not checked: no King standing there can hold new ones back.
void ancientKings(int player = 1) {
    if (laneValue(player, fKings) <= 0) return;
    vector stall = xsVectorSet(0.1 * laneStallX10(player), 0.1 * laneStallY10(player), 0.0);
    if (xsCreateUnit(cKing, player, stall, false, true, false) >= 0) laneSet(player, fKings, laneValue(player, fKings) - 1);
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
// Towers belong in the build rows. One in the resource area could reach the trade channel
// beside it, so it is removed.
void ancientEconomyTowers(int player = 1) {
    ancientUnitArray = xsGetPlayerUnitIds(player, cTowerClass, ancientUnitArray);
    bool removed = false;
    for (index = 0; < xsArrayGetSize(ancientUnitArray)) {
        int tower = xsArrayGetInt(ancientUnitArray, index);
        vector position = xsGetUnitPosition(tower);
        float x = xsVectorGetX(position);
        float y = xsVectorGetY(position);
        if ((x >= laneEconomyX1(player)) && (x < laneEconomyX2(player) + 1) && (y >= laneEconomyY1(player)) && (y < laneEconomyY2(player) + 1)) {
            xsRemoveUnit(tower);
            removed = true;
        }
    }
    if (removed) ancientMessage(player, cMessageEconomyTower);
}

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
    int price = ancientKingPrice(player);
    int kings = 0;
    while (gold >= price) {
        gold = gold - price;
        kings = kings + 1;
    }
    if (kings == 0) return;
    xsSetPlayerAttribute(player, cAttributeGold, gold);
    laneSet(player, fKings, laneValue(player, fKings) + kings);
    ancientMessage(player, cMessageGold);
}

void ancientKillRewards(int player = 1) {
    int kills = ancientWaveKills(player);
    int paid = laneValue(player, fKills);
    int rewards = 0;
    while ((paid + rewards + 1) * cKillsPerReward <= kills) {
        rewards = rewards + 1;
    }
    if (rewards == 0) return;
    // Each reward pays the scaled total so far less what was paid before, so rounding never
    // accumulates.
    int percent = civKillPercent(xsGetPlayerCivilization(player));
    int total = paid + rewards;
    int stone = total * cKillStone * percent / 100 - paid * cKillStone * percent / 100;
    int wood = total * cKillWood * percent / 100 - paid * cKillWood * percent / 100;
    xsSetPlayerAttribute(player, cAttributeStone, xsPlayerAttribute(player, cAttributeStone) + stone);
    xsSetPlayerAttribute(player, cAttributeWood, xsPlayerAttribute(player, cAttributeWood) + wood);
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
                ancientAddAttack(player, investFamily(invest), amount);
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

// The lane that takes this turn in a second. The order rotates and reverses every other
// second, so over fourteen seconds each lane goes first against every other seven times and
// no slot wins contested siege claims more often.
int ancientTurn(int clock = 0, int turn = 0) {
    if (clock % 2 == 0) return ((clock + turn) % 7 + 1);
    return (7 - (clock + turn) % 7);
}

void ancientEconomy(int state = 0) {
    int clock = xsTriggerVariable(vEconomy);
    if (state != sSetup) {
        clock = clock + 1;
        xsSetTriggerVariable(vEconomy, clock);
    }
    for (turn = 0; < 7) {
        int player = ancientTurn(clock, turn);
        if ((laneValue(player, fActive) == 1) && (laneValue(player, fInitialized) == 1)) {
            ancientControl(player);
            ancientShop(player);
            ancientUpgrades(player);
            ancientTransfers(player);
            ancientEconomyTowers(player);
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
    // The current wave's enemies are counted every second, every type each cSweepTicks seconds.
    int live = -1;
    if (xsTriggerVariable(vWave) >= 0) live = waveKind(ancientTemplate(xsTriggerVariable(vWave)));
    int slice = (xsTriggerVariable(vEconomy) + xsTriggerVariable(vSetupElapsed)) % cSweepTicks;
    int losses = ancientCollect(live, slice);
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
    // The siege clock runs before the shop, so a claim made this second keeps its full warning.
    ancientSiege();
    ancientEconomy(state);
    // Losses resolve as one batch on the next clock event.
    if (xsTriggerVariable(vStage) == cStageSudden) ancientDrain();
    // Native requests are acknowledged once. Waiting preserves a common wave schedule.
    bool ready = (xsTriggerVariable(vEndlessRequest) == 0);
    for (player = 1; <= 7) {
        if ((laneValue(player, fActive) == 1) &&
            ((laneValue(player, fInitialized) == 0) || (laneValue(player, fSpawn) > 0))) ready = false;
        // Once the lane's own setup has run, its granted purchases are placed and its native
        // effect set requested, once; -1 records that there is none to request.
        if ((laneValue(player, fActive) == 1) && (laneValue(player, fInitialized) == 1) && (laneValue(player, fProfile) == 0)) {
            int civilization = xsGetPlayerCivilization(player);
            ancientGrant(player, civilization);
            ancientCivAttack(player, civilization);
            int native = civNative(civilization);
            if (native > 0) laneSet(player, fProfile, native);
            else laneSet(player, fProfile, -1);
        }
    }
    if (ready == false) return;
    if (state == sSetup) {
        xsSetTriggerVariable(vSetupElapsed, xsTriggerVariable(vSetupElapsed) + 1);
        // A selection this second has begun preparation already; the second was the window's.
        if (xsTriggerVariable(vPhase) != sSetup) return;
    }
    if ((state == sSetup) || (state == sPreparation)) {
        int remaining = xsTriggerVariable(vRemaining) - 1;
        xsSetTriggerVariable(vRemaining, remaining);
        if (state == sSetup) {
            // The on-screen countdown starts with the window's first counted second.
            if (remaining == cChoice - 1) xsSetTriggerVariable(vWaveDisplay, 3);
            xsSetTriggerVariable(vCountdown, remaining + cPreparation);
        } else xsSetTriggerVariable(vCountdown, remaining);
        xsSetTriggerVariable(vDisplayWave, xsTriggerVariable(vWave) + 2);
        if (remaining <= 0) {
            if (state == sSetup) {
                ancientLock();
                ancientBeginPreparation();
            } else ancientStartWave();
        }
        return;
    }
    int wave = xsTriggerVariable(vWave);
    int pattern = ancientTemplate(wave);
    int elapsed = xsTriggerVariable(vElapsed) + 1;
    int batches = xsTriggerVariable(vBatches);
    int cooldown = xsTriggerVariable(vSpawnClock);
    int alive = 0;
    bool capacity = true;
    for (defender = 1; <= 7) {
        if (laneValue(defender, fActive) == 1) {
            int count = laneValue(defender, fCount);
            alive = alive + count;
            if (count + waveCount(pattern) > cEnemyCap) capacity = false;
        }
    }
    // A batch waits for the native triggers to configure the wave's enemies.
    bool configured = (xsTriggerVariable(vConfigured) == pattern + 1);
    if ((batches < waveBatches(pattern)) && (cooldown <= 0) && capacity && configured) {
        int hitpoints = ancientWaveHitPoints(wave);
        for (slot = 1; <= 7) {
            if (laneValue(slot, fActive) == 1) ancientSpawnBatch(slot, pattern, hitpoints);
        }
        xsSetTriggerVariable(vBatches, batches + 1);
        cooldown = waveInterval(pattern);
    }
    xsSetTriggerVariable(vSpawnClock, cooldown - 1);
    xsSetTriggerVariable(vElapsed, elapsed);
    int spawning = waveDuration(pattern) - elapsed;
    if (spawning < 0) spawning = 0;
    xsSetTriggerVariable(vCountdown, spawning);
    // The final batch must already have been acknowledged and all enemies resolved.
    if ((elapsed >= waveDuration(pattern)) && (batches == waveBatches(pattern)) && (alive == 0)) {
        ancientWaveCleared(wave);
        ancientNextWave(wave);
    }
}
