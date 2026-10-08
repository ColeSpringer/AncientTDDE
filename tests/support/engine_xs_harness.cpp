// Only DE API boundaries are substituted; the generated XS drives every transition.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>
using string = std::string;
using vector = std::array<float, 3>;
struct Unit { int type; vector pos; float hp = 100; int owner = 8; int garrison = -1; };
std::map<int, Unit> units;
std::array<int, 256> variables{};
std::array<bool, 9> occupied{};
constexpr int cPlayerTypeHuman = 1;
constexpr int cPlayerTypeComputer = 3;
constexpr int cArcherClass = 900;
constexpr int cSentinelEndClass = 965;
constexpr int cAttributeFood = 0;
constexpr int cAttributeWood = 1;
constexpr int cAttributeStone = 2;
constexpr int cAttributeGold = 3;
constexpr int cAttributeKills = 20;
// Kept by the enemy (player 8): how many of its units each player has killed.
constexpr int cAttributeKillsByPlayer1 = 326;
constexpr int cTechStateDisabled = -1;
constexpr int cTechStateDone = 3;
constexpr int cHitpoints = 0;
constexpr int cVillagerClass = 904;
constexpr int cTowerClass = 952;
std::array<int, 9> playerTypes{};
std::array<std::map<int, float>, 9> attributes{};
std::map<std::pair<int, int>, int> techStates;
std::array<float, 9> outpostHitpoints{500, 500, 500, 500, 500, 500, 500, 500, 500};
std::vector<std::pair<int, int>> researched;
std::vector<string> chat;
std::vector<std::vector<int>> arrays;
// Placed map objects keep their scenario IDs, so generated IDs start above them.
int sequence = 100000;
int xsTriggerVariable(int id) { return variables.at(id); }
void xsSetTriggerVariable(int id, int value) { variables.at(id) = value; }
bool xsGetPlayerInGame(int player) { return occupied.at(player); }
int xsGetPlayerType(int player) { return playerTypes.at(player); }
float xsPlayerAttribute(int player, int attribute) { return attributes.at(player)[attribute]; }
void xsSetPlayerAttribute(int player, int attribute, float value) { attributes.at(player)[attribute] = value; }
int xsGetTechState(int tech, int player) {
    auto found = techStates.find({tech, player});
    return found == techStates.end() ? 1 : found->second;
}
bool xsResearchTechnology(int tech, bool, bool, int player) {
    researched.push_back({tech, player});
    techStates[{tech, player}] = cTechStateDone;
    return true;
}
float xsGetObjectAttribute(int player, int object, int attribute, int = -1) {
    if (object != 598 || attribute != cHitpoints) { std::cerr << "Unexpected object attribute\n"; std::exit(1); }
    return outpostHitpoints.at(player);
}
// Stock classes of the defense-player objects used below. DE addresses class N as 900 + N.
int classOf(int type) {
    switch (type) {
        case 17: return 2;                                // Trade Cog
        case 68: case 129: case 130: case 131: return 3;  // Mill and its age forms
        case 82: case 598: return 3;                      // Castle, Outpost
        case 83: case 293: return 4;                      // Villager
        case 125: return 18;                              // Monk
        case 128: return 19;                              // Trade Cart
        case 601: return 30;                              // Flag
        case 79: case 234: case 235: case 236: return 52; // Watch Tower, Guard Tower, Keep, Bombard Tower
        case 546: case 441: return 12;                    // Light Cavalry, Hussar
        case 1103: case 529: return 22;                   // Fire Galley, Fire Ship
        case 331: return 51;                              // Packed Trebuchet
        case 42: return 54;                               // Trebuchet
        case 434: return 59;                              // King
    }
    std::cerr << "No class recorded for object " << type << '\n';
    std::exit(1);
}
// DE documents object and class queries only; there is no documented all-objects wildcard.
int xsGetPlayerUnitIds(int player, int objectOrClass, int target = -1) {
    if (objectOrClass < 0) {
        std::cerr << "Unit queries need a documented object or class ID\n";
        std::exit(1);
    }
    if (target < 0) { target = arrays.size(); arrays.emplace_back(); }
    arrays.at(target).clear();
    bool byClass = objectOrClass >= cArcherClass && objectOrClass < cSentinelEndClass;
    for (auto &[id, u] : units) {
        if (u.owner != player) continue;
        int match = byClass ? cArcherClass + classOf(u.type) : u.type;
        if (match == objectOrClass) arrays[target].push_back(id);
    }
    return target;
}
int xsArrayCreateInt(int size, int value, string) { arrays.emplace_back(size, value); return arrays.size() - 1; }
bool xsArraySetInt(int id, int index, int value) { arrays.at(id).at(index) = value; return true; }
std::vector<std::vector<float>> floatArrays;
int xsArrayCreateFloat(int size, float value, string) { floatArrays.emplace_back(size, value); return floatArrays.size() - 1; }
bool xsArraySetFloat(int id, int index, float value) { floatArrays.at(id).at(index) = value; return true; }
float xsArrayGetFloat(int id, int index) { return floatArrays.at(id).at(index); }
int xsArrayGetSize(int id) { return arrays.at(id).size(); }
int xsArrayGetInt(int id, int index) { return arrays.at(id).at(index); }
float xsGetUnitHitpoints(int id) { return units.at(id).hp; }
bool xsSetUnitHitpoints(int id, float hp) {
    if (!units.count(id)) return false;
    units[id].hp = hp;
    return true;
}
int xsGetGarrisonedInUnitId(int id) { return units.at(id).garrison; }
int xsGetUnitType(int id) { return units.at(id).type; }
vector xsGetUnitPosition(int id) { return units.at(id).pos; }
vector xsVectorSet(float x, float y, float z) { return {x, y, z}; }
std::array<int, 9> kingsCreated{};
std::array<std::map<int, int>, 9> created{};
// A unit, building or object on the spot blocks a collision-checked creation, as in DE.
int xsCreateUnit(int type, int owner, vector pos, bool, bool, bool checkCollision) {
    if (checkCollision)
        for (auto &[id, u] : units)
            if (std::abs(u.pos[0] - pos[0]) < 0.5f && std::abs(u.pos[1] - pos[1]) < 0.5f) return -1;
    int id = sequence++;
    units.emplace(id, Unit{type, pos, 100, owner});
    ++created[owner][type];
    if (type == 434) ++kingsCreated[owner];
    return id;
}
float xsVectorGetX(vector pos) { return pos[0]; }
float xsVectorGetY(vector pos) { return pos[1]; }
bool xsRemoveUnit(int id) { return units.erase(id) == 1; }
void xsChatData(string message, int = -1) { chat.push_back(message); }
// The lobby's difficulty setting, as xsGetDifficulty reports it: Moderate unless a case says otherwise.
int lobbyDifficulty = 2;
int xsGetDifficulty() { return lobbyDifficulty; }
// Each player's civilization, as DE numbers them: the neutral test civilization (101) unless
// a case says otherwise, so no case depends on a real profile staying neutral.
std::array<int, 9> civilizations{101, 101, 101, 101, 101, 101, 101, 101, 101};
int xsGetPlayerCivilization(int player) { return civilizations.at(player); }
int xsGetObjectCount(int player, int type) {
    int count = 0;
    for (auto &[id, u] : units) if (u.owner == player && u.type == type && u.hp > 0) ++count;
    return count;
}
// EMBEDDED_XS
void require(bool ok, string message) { if (!ok) { std::cerr << message << '\n'; std::exit(1); } }
int lane(int player, int field) { return xsTriggerVariable(laneVariable(player, field)); }
void setLane(int player, int field, int value) { xsSetTriggerVariable(laneVariable(player, field), value); }
int phase() { return xsTriggerVariable(vPhase); }
std::array<int, 9> grants{}, spawns{}, cleanups{}, attacks{};
std::array<std::vector<int>, 9> bought{};
// Message codes each lane's native message triggers delivered to its player.
std::array<std::vector<int>, 9> sent{};
std::array<int, 9> berryMills{};
bool near(const Unit &u, int x10, int y10) {
    return std::abs(u.pos[0] - x10 / 10.0f) < 0.5f && std::abs(u.pos[1] - y10 / 10.0f) < 0.5f;
}
void resetXsBuffers() {
    arrays.clear(); floatArrays.clear();
    ancientUnitArray=-1; ancientPadCounts=-1; ancientRelicArray=-1; ancientLeakCounts=-1;
    ancientKingIds=-1; ancientKingX=-1; ancientKingY=-1; ancientKingSampled=-1; ancientKingPads=-1;
    ancientKingStill=-1; ancientSampleX=-1; ancientSampleY=-1; ancientSampleStill=-1; ancientLastNotice=-1;
    ancientSpawnArray=-1; ancientVillagerArray=-1;
}
// Endless growth levels and armor steps the native triggers applied, and countdowns shown.
std::vector<int> endlessLevels;
int armorSteps = 0, waveTimers = 0, timerClears = 0;
// Native triggers acknowledge one request per lane each pass, as the generated ones do.
void nativeEffects() {
    if (xsTriggerVariable(vEndlessRequest) > 0) {
        endlessLevels.push_back(xsTriggerVariable(vEndlessRequest));
        xsSetTriggerVariable(vEndlessRequest, 0);
    }
    if (xsTriggerVariable(vArmorRequest) > 0) {
        ++armorSteps;
        xsSetTriggerVariable(vArmorRequest, xsTriggerVariable(vArmorRequest) - 1);
    }
    if (xsTriggerVariable(vWaveDisplay) == 1) ++waveTimers;
    if (xsTriggerVariable(vWaveDisplay) == 2) ++timerClears;
    xsSetTriggerVariable(vWaveDisplay, 0);
    for (int p=1; p<=7; ++p) {
        if (lane(p, fActive) && !lane(p, fInitialized)) { ++grants[p]; setLane(p, fInitialized, 1); }
        if (lane(p, fCleanup)) {
            ancientCleanupLane(p, berryMills[p]);
            ++cleanups[p]; setLane(p, fCleanup, 0);
        }
        if (lane(p, fActive) && lane(p, fPurchase)) {
            int purchase = lane(p, fPurchase);
            bought[p].push_back(purchase);
            // Bought villagers and traders walk off their arrival spots.
            int key = p * cSpawnStride + purchase;
            for (int entry = spawnStart(key); entry < spawnStart(key) + spawnCount(key); ++entry)
                for (auto &[id, u] : units)
                    if (u.owner == p && (u.type == 83 || u.type == 128 || u.type == 17 || u.type == 546 || u.type == 1103) && near(u, spawnX10(entry), spawnY10(entry)))
                        u.pos[1] += 3;
            setLane(p, fPurchase, 0);
        }
        // New Kings walk from the stall into the shop; transferred villagers clear the arrival.
        if (lane(p, fActive)) {
            for (auto &[id, u] : units) {
                if (u.owner == p && u.type == cKing && near(u, laneStallX10(p), laneStallY10(p))) u.pos[1] = 8.5f;
                for (int t = 0; t < cTransferCount; ++t)
                    if (u.owner == p && classOf(u.type) == 4 && near(u, transferX10(p * cTransferCount + t), transferY10(p * cTransferCount + t))) u.pos[1] += 2;
            }
        }
        if (lane(p, fActive) && lane(p, fAttack) > 0) { ++attacks[p]; setLane(p, fAttack, lane(p, fAttack) - 1); }
        if (lane(p, fActive) && lane(p, fMessage)) { sent[p].push_back(lane(p, fMessage)); setLane(p, fMessage, 0); }
        int wave = lane(p, fSpawn) - 1;
        if (lane(p, fActive) && wave >= 0) {
            spawns[p] += waveCount(wave);
            for (int i=0; i<waveCount(wave); ++i)
                units.emplace(sequence++, Unit{waveUnit(wave), {float(laneSpawnX(p)), float(laneY(p)), 0}});
            setLane(p, fSpawn, 0);
        }
    }
}
// Waves clear the field each second; a lane's own Kings and life display stay.
void clearEnemies() {
    for (auto it = units.begin(); it != units.end();) {
        if (it->second.owner == 8) it = units.erase(it); else ++it;
    }
}
void tick(bool clear=false) { if (clear) clearEnemies(); ancientTick(); nativeEffects(); }
void start(std::initializer_list<int> humans) {
    occupied.fill(true);
    playerTypes.fill(cPlayerTypeComputer);
    for (int p:humans) playerTypes[p]=cPlayerTypeHuman;
    for (int p=1; p<=7; ++p) units.emplace(laneLife(p), Unit{598, {134.5f, 67.5f + 3 * (p - 1), 0}, 500, p});
    tick();
}
void advanceTo(int desired) {
    for(int n=0; n<10000 && phase()!=desired; ++n) tick(true);
    require(phase()==desired, "Expected state was not reached");
}
void advanceEconomy(int seconds) {
    int target = xsTriggerVariable(vEconomy) + seconds;
    for(int n=0; n<10000 && xsTriggerVariable(vEconomy)<target; ++n) tick(true);
    require(xsTriggerVariable(vEconomy)==target, "Economy clock did not advance");
}
void kingsOn(int player, int purchase, int count) {
    float x = (shopX1(purchase) + shopX2(purchase)) / 2 + 0.5f;
    float y = (shopY1(purchase) + shopY2(purchase)) / 2 + 0.5f;
    for (int i=0; i<count; ++i) units.emplace(sequence++, Unit{cKing, {x, y, 0}, 75, player});
}
// Kings walk 1.32 tiles per game second in DE; the clock samples them once per second.
constexpr float KING_SPEED = 1.32f;
std::vector<int> kingsAt(int player, float x, float y, int count, float spacing) {
    std::vector<int> ids;
    for (int i=0; i<count; ++i) { ids.push_back(sequence); units.emplace(sequence++, Unit{cKing, {x - spacing * i, y, 0}, 75, player}); }
    return ids;
}
void walk(const std::vector<int> &ids, float dx, float dy) {
    for (int id : ids) if (units.count(id)) { units[id].pos[0] += dx; units[id].pos[1] += dy; }
}
int kingsOnPad(int player, int purchase) {
    int found = 0;
    for (auto &[id, u] : units) {
        if (u.owner == player && u.type == cKing && u.pos[0] >= shopX1(purchase) && u.pos[0] < shopX2(purchase) + 1
            && u.pos[1] >= shopY1(purchase) && u.pos[1] < shopY2(purchase) + 1) ++found;
    }
    return found;
}
int mentions(string text) {
    return std::count_if(chat.begin(), chat.end(), [&](const string &m) { return m.find(text) != string::npos; });
}
int told(int player, int code) { return std::count(sent[player].begin(), sent[player].end(), code); }
int toldAnything(int player) { return sent[player].size(); }
float resource(int player, int attribute) { return attributes.at(player)[attribute]; }
void select(int player, int control) { setLane(player, fControl, control); }
// Run every wave to its end, clearing the field each second, until the game is decided.
void finishSchedule() {
    for(int n=0; n<20000 && phase()!=sVictory && phase()!=sDefeat; ++n) tick(true);
}
// Clear waves until the given wave has started.
void reachWave(int wave) {
    for(int n=0; n<40000 && xsTriggerVariable(vWave)<wave && phase()!=sVictory && phase()!=sDefeat; ++n) tick(true);
    require(xsTriggerVariable(vWave)==wave, "The wave was not reached");
}
// A competitive game past its first wave, so the run options are fixed. PvP is off unless
// the chooser switches it on first.
void competitive(std::initializer_list<int> humans, bool pvp=true) {
    start(humans);
    if (pvp) { select(xsTriggerVariable(vChooser), cControlPvpOn); tick(); }
    advanceTo(sWave);
}
int unitsOf(int player, int type) {
    int count = 0;
    for (auto &[id, u] : units) if (u.owner == player && u.type == type) ++count;
    return count;
}
int own(std::initializer_list<int> purchases) {
    int owned = 0;
    for (int purchase : purchases) owned += shopMask(purchase);
    return owned;
}
int main(int argc, char** argv) {
    require(argc == 2, "Need case"); string test=argv[1];
    if(test=="berry_mills") {
        // Each lane owns a mill plus one object from every other class it starts with.
        std::array<std::vector<int>, 9> laneUnits{};
        for(int p=1;p<=7;++p) {
            berryMills[p]=sequence;
            units.emplace(sequence++, Unit{68, {84, float(laneY(p)), 0}, 100, p});
            for(int type: {293, 79, 128, 17, 601, 434}) {
                laneUnits[p].push_back(sequence);
                units.emplace(sequence++, Unit{type, {85.5, float(laneY(p))-1.5f, 0}, 100, p});
            }
        }
        int gaia=sequence++;
        units.emplace(gaia, Unit{68, {161, 195, 0}, 100, 0});
        int keeper=sequence++;
        units.emplace(keeper, Unit{434, {25.5, 2.5, 0}, 100, 8});
        start({2,7});
        for(int p=1;p<=7;++p) {
            require(units.count(berryMills[p])==1, "A player's berry mill was removed at startup");
            require(units.at(berryMills[p]).owner==p, "Berry mill ownership changed");
            bool human=p==2 || p==7;
            for(int id: laneUnits[p])
                require(units.count(id)==human, "Startup cleanup did not distinguish human and AI units");
            require(units.count(laneLife(p))==human, "Startup cleanup kept an AI lane's life display");
        }
        units.at(berryMills[2]).type=131;
        int extraMill=sequence++;
        units.emplace(extraMill, Unit{68, {80, float(laneY(2)), 0}, 100, 2});
        resetXsBuffers();
        setLane(2, fLives, 0); tick();
        require(units.count(berryMills[2])==1 && units.at(berryMills[2]).owner==2,
                "Elimination removed or transferred the upgraded berry mill");
        require(!units.count(extraMill), "Elimination left a second mill behind");
        for(int id: laneUnits[2]) require(!units.count(id), "Elimination left other player units behind");
        require(units.count(gaia)==1 && units.count(keeper)==1 && units.count(laneUnits[7][0])==1,
                "Cleanup removed another owner's units");
        auto remaining=units.size();
        ancientCleanupLane(2, berryMills[2]);
        require(units.size()==remaining, "Repeating cleanup changed the remaining units");
        units.erase(berryMills[1]);
        ancientCleanupLane(1, berryMills[1]);
        require(!units.count(berryMills[1]), "Cleanup recreated a missing mill");
    } else if(test=="slots") {
        start({2,7}); require(xsTriggerVariable(vParticipants)==2, "Nonconsecutive slots miscounted");
        advanceTo(sWave); for(int n=0;n<20;++n) tick(true);
        require(spawns[2]==spawns[7] && spawns[2]>0, "Active lanes received different schedules");
        for(int p:{1,3,4,5,6}) {
            require(!grants[p] && !kingsCreated[p] && !spawns[p], "AI filler was paid or spawned");
            require(cleanups[p]==1, "AI filler was not cleared exactly once");
        }
    } else if(test=="ai_departures") {
        start({7});
        require(xsTriggerVariable(vParticipants)==1, "AI fillers turned solo into competition");
        advanceTo(sWave);
        for(int n=0;n<10000 && xsTriggerVariable(vWave)<1;++n) tick(true);
        require(xsTriggerVariable(vWave)==1 && phase()==sWave, "Did not reach the second wave");
        for(int p=1;p<=6;++p) occupied[p]=false;
        tick(true); tick(true);
        require(phase()==sWave && xsTriggerVariable(vWinner)==0, "AI departures awarded early solo victory");
        require(lane(7,fActive)==1 && grants[7]==1, "Human in the last slot was not initialized");
    } else if(test=="no_humans") {
        start({}); tick();
        require(phase()==sDefeat && xsTriggerVariable(vParticipants)==0, "AI-only lobby started human lanes");
        for(int p=1;p<=7;++p) require(!grants[p] && cleanups[p]==1, "AI-only lane was initialized");
    } else if(test=="initialize") {
        start({1}); for(int n=0;n<200;++n) tick(true);
        require(grants[1]==1, "Initialization was repeated");
        require(lane(1,fLives)==cLives, "Initialization or ordinary ticks changed lives");
    } else if(test=="solo") {
        start({7}); advanceTo(sBoss);
        require(phase()!=sVictory, "Early solo victory");
        for(int n=0;n<10000 && !(xsTriggerVariable(vWave)==cWaveCount-1 && xsTriggerVariable(vElapsed)>=waveDuration(cWaveCount-1)-1);++n) tick(true);
        units.emplace(sequence++, Unit{waveUnit(cWaveCount-1), {20, float(laneY(7)), 0}});
        for(int n=0;n<20;++n) tick();
        require(phase()!=sVictory, "Finale timer awarded victory with an enemy alive");
        tick(true); require(phase()==sVictory && xsTriggerVariable(vWinner)==7, "Cleared solo finale did not win");
    } else if(test=="defeat" || test=="simultaneous") {
        start(test=="defeat" ? std::initializer_list<int>{7} : std::initializer_list<int>{1,7});
        setLane(7,fLives,0); if(test=="simultaneous") setLane(1,fLives,0);
        tick(); require(phase()==sElimination, "Missing batch elimination state");
        tick(); require(phase()==sDefeat && xsTriggerVariable(vWinner)==8, "Empty field selected a human winner");
    } else if(test=="survivor" || test=="resign") {
        start({2,7});
        if(test=="resign") occupied[2]=false; else setLane(2,fLives,0);
        tick(); tick();
        require(phase()==sVictory && xsTriggerVariable(vWinner)==7, "Last survivor did not win");
        int paid=kingsCreated[2];
        attributes[2][cAttributeGold]=9000;
        for(int n=0;n<30;++n) tick();
        require(kingsCreated[2]==paid && lane(2,fActive)==0, "Eliminated lane still receives Kings");
    } else if(test=="sudden") {
        start({1,7});
        reachWave(cWaveCount);
        require(xsTriggerVariable(vStage)==cStageSudden, "Survivors of the finale did not enter sudden death");
        int lives=lane(1,fLives); for(int n=0;n<cSuddenInterval;++n) tick(true);
        require(lane(1,fLives)<lives && lane(1,fLives)==lane(7,fLives), "Sudden death pressure is asymmetric");
        require(spawns[1]>0 && spawns[1]==spawns[7], "Sudden death waves differ between survivors");
        advanceTo(sDefeat); require(xsTriggerVariable(vWinner)==8, "Tied sudden death favored a slot");
    } else if(test=="sudden_survivor") {
        start({1,7});
        reachWave(cWaveCount);
        setLane(1, fLives, 1);
        for(int n=0;n<2*cSuddenInterval && phase()!=sVictory;++n) tick(true);
        require(phase()==sVictory && xsTriggerVariable(vWinner)==7, "The last survivor of sudden death did not win");
    } else if(test=="endless_continues") {
        start({4});
        select(4, cControlEndless); tick();
        reachWave(cWaveCount + 1);
        require(phase()!=sVictory && xsTriggerVariable(vStage)==cStageEndless, "Endless stopped at the finale");
        require(mentions("Endless wave 1 (wave 16)")==1 && mentions("Endless wave 2 (wave 17)")==1,
                "Endless waves were not announced");
        int first = endlessTemplate(0), second = endlessTemplate(1);
        require(spawns[4] > 0 && xsTriggerVariable(vConfigured)==second + 1, "Endless waves did not spawn their template");
        require(first != second, "Endless waves did not move through their templates");
        require(waveTimers >= 2, "Endless waves were not counted down");
    } else if(test=="endless_growth") {
        start({4});
        select(4, cControlEndless); tick();
        reachWave(cWaveCount);
        require(endlessLevels==std::vector<int>{1} && armorSteps==1, "The first endless wave was not configured once");
        reachWave(cWaveCount + cEndlessTemplates);
        require(endlessLevels==std::vector<int>({1, 2}) && armorSteps==cEndlessTemplates + 1,
                "A new round of templates did not grow, or armor did not rise every wave");
        require(xsTriggerVariable(vArmor)==(cEndlessTemplates + 1) * cArmorStep, "Armor total was not kept");
        int hitpoints = endlessHitPoints((xsTriggerVariable(vDifficulty) * cEndlessTemplates) * cEndlessLevels + 1);
        require(mentions(ancientText(hitpoints) + " HP each")>=1, "The grown hit points were not announced");
    } else if(test=="endless_waits") {
        start({4});
        select(4, cControlEndless); tick();
        reachWave(cWaveCount - 1);
        for(int n=0;n<10000 && phase()!=sPreparation;++n) tick(true);
        // Without the native triggers, the endless wave starts but waits for its configuration.
        for(int n=0;n<10000 && xsTriggerVariable(vWave)<cWaveCount;++n) { clearEnemies(); ancientTick(); }
        require(xsTriggerVariable(vEndlessRequest)==1 && xsTriggerVariable(vArmorRequest)==1, "The endless wave did not ask for its configuration");
        int before = spawns[4];
        for(int n=0;n<5;++n) { clearEnemies(); ancientTick(); }
        require(spawns[4]==before && lane(4,fSpawn)==0, "An endless wave spawned before its configuration applied");
        nativeEffects(); nativeEffects();
        for(int n=0;n<5;++n) tick(true);
        require(spawns[4]>before, "The endless wave did not spawn after its configuration applied");
    } else if(test=="endless_result") {
        start({4});
        select(4, cControlEndless); tick();
        reachWave(cWaveCount + 2);
        attributes[8][cAttributeKillsByPlayer1+3]=4567;
        setLane(4, fLives, 0); tick(); tick();
        require(phase()==sDefeat, "The endless run did not end when its lane fell");
        string minutes = ancientCount((xsTriggerVariable(vEconomy) + cSetup) / 60, "game minute", "game minutes");
        require(mentions("Result: Endless run on Normal: 17 waves cleared (2 endless), 0 lives left, 4567 kills, " + minutes + ".")==1,
                "The endless result was not shown");
    } else if(test=="resume_endless") {
        start({4});
        select(4, cControlEndless); tick();
        reachWave(cWaveCount + 1);
        for(int n=0;n<20;++n) tick(true);
        auto saved=variables; auto savedUnits=units; auto savedAttributes=attributes; auto savedSpawns=spawns;
        auto savedLevels=endlessLevels; int savedArmor=armorSteps;
        for(int n=0;n<400;++n) tick(true);
        auto expected=variables; auto expectedSpawns=spawns; auto expectedLevels=endlessLevels; int expectedArmor=armorSteps;
        variables=saved; units=savedUnits; attributes=savedAttributes; spawns=savedSpawns;
        endlessLevels=savedLevels; armorSteps=savedArmor;
        resetXsBuffers();
        for(int n=0;n<400;++n) tick(true);
        require(variables==expected && spawns==expectedSpawns, "Reload changed endless progress or spawns");
        require(endlessLevels==expectedLevels && armorSteps==expectedArmor, "Reload repeated or lost endless growth");
    } else if(test=="resume") {
        start({2,7});
        setLane(2, fOwned, own({cBuyGold1000, cBuyKingEveryMinute, cBuyAttack1Every5}));
        advanceTo(sWave); for(int n=0;n<27;++n) tick(true);
        kingsOn(7, cBuyTowerAttack10, 3);
        auto saved=variables; auto savedUnits=units; auto savedAttributes=attributes;
        auto savedKings=kingsCreated; auto savedSpawns=spawns; auto savedBought=bought; auto savedAttacks=attacks;
        for(int n=0;n<130;++n) tick(true);
        auto expected=variables; auto expectedAttributes=attributes; auto expectedKings=kingsCreated;
        auto expectedSpawns=spawns; auto expectedBought=bought; auto expectedAttacks=attacks;
        variables=saved; units=savedUnits; attributes=savedAttributes;
        kingsCreated=savedKings; spawns=savedSpawns; bought=savedBought; attacks=savedAttacks;
        resetXsBuffers();
        for(int n=0;n<130;++n) tick(true);
        require(variables==expected && attributes==expectedAttributes, "Reload changed progress, timers or resources");
        require(kingsCreated==expectedKings && spawns==expectedSpawns, "Reload changed Kings or spawns");
        require(bought==expectedBought && attacks==expectedAttacks, "Reload repeated or lost purchases");
        require(grants[2]==1 && grants[7]==1, "Reload repeated bonuses");
    } else if(test=="cap") {
        start({1,7}); advanceTo(sWave);
        for(int i=0;i<cEnemyCap;++i) units.emplace(sequence++,Unit{waveUnit(0), {20,float(laneY(1)),0}});
        int a=spawns[1], b=spawns[7]; for(int n=0;n<20;++n) tick();
        require(spawns[1]==a && spawns[7]==b, "Cap exceeded or shared composition diverged");
        tick(true); require(spawns[1]>a && spawns[1]==spawns[7], "Spawn did not resume together");
    } else if(test=="leaks") {
        start({2,7});
        for(int p:{2,7}) for(int i=0;i<4;++i) units.emplace(sequence++,Unit{waveUnit(0),{float(laneExitX(p)),float(laneY(p)),0}});
        tick(); require(lane(2,fLives)==cLives-4 && lane(7,fLives)==cLives-4, "Leaks were not counted exactly once");
        tick(); require(lane(2,fLives)==cLives-4, "Leak charged twice");
    } else if(test=="first_wave") {
        // Fast is DE's 2x lobby speed: the first pair should arrive about two real minutes in.
        start({7}); int seconds=1;
        while(spawns[7]==0 && seconds<1000) { tick(true); ++seconds; }
        require(seconds>=230 && seconds<=250, "First enemies did not arrive about 240 game seconds in");
    } else if(test=="exit_arrival") {
        // A DE trial left a militia sent to exit tile (56, 15) standing at (55.97, 15.0).
        start({2,7});
        for(int p:{2,7}) units.emplace(sequence++,Unit{waveUnit(0),{float(laneExitX(p))-0.03f,float(laneY(p)),0}});
        tick(); require(lane(2,fLives)==cLives-1 && lane(7,fLives)==cLives-1,
                        "An enemy that stopped at the exit was not counted as a leak");
    } else if(test=="shop_exact") {
        start({1});
        kingsOn(1, cBuyTowerAttack50, 9);
        for(int n=0;n<cStillSamples;++n) tick();
        require(kingsOnPad(1, cBuyTowerAttack50)==9 && bought[1].empty(), "Kings were taken before they stood still");
        tick(); require(kingsOnPad(1, cBuyTowerAttack50)==2, "The payment was not exactly the price");
        require(bought[1]==std::vector<int>{cBuyTowerAttack50}, "The purchase was not requested once");
        for(int n=0;n<5;++n) tick();
        require(kingsOnPad(1, cBuyTowerAttack50)==2 && bought[1].size()==1, "Leftover Kings bought again");
    } else if(test=="shop_repeat") {
        start({1});
        kingsOn(1, cBuyTowerAttack4, 2);
        for(int n=0;n<4;++n) tick();
        require(kingsOnPad(1, cBuyTowerAttack4)==0, "Two prices were not both paid");
        require(bought[1]==std::vector<int>({cBuyTowerAttack4, cBuyTowerAttack4}), "Repeat purchase not requested twice");
    } else if(test=="shop_walking") {
        start({1});
        kingsOn(1, cBuyTowerAttack4, 1);
        tick();
        for(auto &[id, u] : units) if(u.type==cKing && u.owner==1) u.pos[0] += 100;
        for(int n=0;n<3;++n) tick();
        require(bought[1].empty() && toldAnything(1)==0, "A King passing over a pad bought or warned");
    } else if(test=="shop_insufficient") {
        start({1});
        kingsOn(1, cBuyTowerAttack50, 6);
        for(int n=0;n<5;++n) tick();
        require(kingsOnPad(1, cBuyTowerAttack50)==6 && bought[1].empty(), "A short payment was taken");
    } else if(test=="shop_once") {
        start({1});
        kingsOn(1, cBuyLeftAccursedTower, 1);
        for(int n=0;n<=cStillSamples;++n) tick();
        require(bought[1]==std::vector<int>{cBuyLeftAccursedTower}, "The once-only purchase was not made");
        kingsOn(1, cBuyLeftAccursedTower, 1);
        for(int n=0;n<4;++n) tick();
        require(kingsOnPad(1, cBuyLeftAccursedTower)==1 && bought[1].size()==1, "A once-only purchase was charged twice");
        require(told(1, cMessageOwned)==1 && mentions("already")==0, "The refusal was not told to the player exactly once");
        for(int n=0;n<cNoticeSeconds;++n) tick();
        require(told(1, cMessageOwned)==2, "The refusal was not repeated after the pause");
    } else if(test=="shop_requires") {
        start({1});
        kingsOn(1, cBuyImperialAge, 1);
        for(int n=0;n<3;++n) tick();
        require(bought[1].empty() && kingsOnPad(1, cBuyImperialAge)==1, "Imperial Age was sold before Castle Age");
        require(told(1, cMessageRequires)==1, "The missing requirement was not explained");
        kingsOn(1, cBuyCastleAge, 1);
        for(int n=0;n<6;++n) tick();
        require(bought[1]==std::vector<int>({cBuyCastleAge, cBuyImperialAge}), "Requirement did not unlock the purchase");
    } else if(test=="shop_pending") {
        start({1});
        kingsOn(1, cBuyTowerAttack4, 1);
        for(int n=0;n<cStillSamples;++n) tick();
        ancientTick();
        require(lane(1,fPurchase)==cBuyTowerAttack4, "Purchase not requested");
        kingsOn(1, cBuyTowerAttack10, 2);
        ancientTick(); ancientTick(); ancientTick();
        require(kingsOnPad(1, cBuyTowerAttack10)==2, "A second purchase was paid before the first took effect");
        nativeEffects(); tick(); tick();
        require(bought[1]==std::vector<int>({cBuyTowerAttack4, cBuyTowerAttack10}), "Waiting purchase was lost");
    } else if(test=="shop_relics") {
        start({3});
        int relic=sequence++;
        units.emplace(relic, Unit{cRelic, {laneRelicX2(3)+0.5f, laneRelicY1(3)+0.5f, 0}, 1, 0});
        kingsOn(3, cBuyRelics, 1);
        for(int n=0;n<3;++n) tick();
        require(bought[3].empty() && told(3, cMessageRelics)==1, "Relics were sold over uncollected relics");
        units.erase(relic);
        tick(); tick();
        require(bought[3]==std::vector<int>{cBuyRelics}, "Collected relics did not reopen the purchase");
    } else if(test=="shop_inactive") {
        start({2});
        kingsOn(1, cBuyTowerAttack4, 3);
        for(int n=0;n<4;++n) tick();
        require(bought[1].empty() && kingsOnPad(1, cBuyTowerAttack4)==3, "A computer-filled lane bought");
    } else if(test=="gold_kings") {
        start({3});
        attributes[3][cAttributeGold]=2*kingGold(xsTriggerVariable(vDifficulty))+600;
        tick();
        require(resource(3, cAttributeGold)==600, "Gold was not converted in whole Kings");
        require(told(3, cMessageGold)==1 && mentions("onverted")==0, "The conversion was not told to its player alone");
        tick();
        require(kingsCreated[3]==2 && lane(3,fKings)==0, "Converted Kings did not arrive");
    } else if(test=="kill_rewards") {
        start({4});
        attributes[8][cAttributeKillsByPlayer1+3]=cKillsPerReward-1;
        tick(); require(resource(4, cAttributeStone)==0, "A reward came early");
        attributes[8][cAttributeKillsByPlayer1+3]=cKillsPerReward;
        tick();
        require(resource(4, cAttributeStone)==cKillStone && resource(4, cAttributeWood)==cKillWood, "Kill reward wrong");
        attributes[8][cAttributeKillsByPlayer1+3]=cKillsPerReward*cRewardsPerKing;
        tick(); tick();
        require(resource(4, cAttributeStone)==cKillStone*cRewardsPerKing, "Kill rewards were not all paid");
        require(kingsCreated[4]==1 && told(4, cMessageKillKing)==1, "The kill King was not granted and announced once");
        tick(); require(kingsCreated[4]==1, "Kill rewards repeated");
    } else if(test=="wave_kings") {
        start({1,7}); advanceTo(sWave);
        for(int n=0;n<10000 && phase()==sWave;++n) tick(true);
        tick();
        require(kingsCreated[1]==cWaveKings && kingsCreated[7]==cWaveKings, "Clearing a wave did not pay its Kings");
        require(kingsCreated[2]==0, "A computer lane was paid for a wave");
    } else if(test=="investments") {
        // On Hard a King costs more than the gold paid out, so none of it is converted.
        lobbyDifficulty=1;
        start({1});
        require(kingGold(xsTriggerVariable(vDifficulty)) > 2000, "The case needs a King price above the gold paid");
        setLane(1, fOwned, own({cBuyGold1000, cBuyKingEveryMinute}));
        for(int n=0;n<cSetup;++n) tick(true);
        require(xsTriggerVariable(vEconomy)<=1 && kingsCreated[1]==0, "Investments paid during setup");
        advanceEconomy(240-xsTriggerVariable(vEconomy));
        tick(true);
        require(resource(1, cAttributeGold)==2000, "Gold investment did not pay every two minutes");
        require(kingsCreated[1]==4 && lane(1, fKings)==0, "King investment did not pay every minute");
    } else if(test=="attack_investment") {
        start({1});
        setLane(1, fOwned, own({cBuyAttack1Every5}));
        advanceTo(sPreparation);
        advanceEconomy(30-xsTriggerVariable(vEconomy));
        tick(true);
        require(attacks[1]==6, "Periodic tower attack did not arrive every five seconds");
    } else if(test=="repair") {
        start({1});
        setLane(1, fOwned, own({cBuyRepair}));
        advanceTo(sPreparation);
        setLane(1, fLives, cLives-3);
        attributes[1][cAttributeStone]=2*cRepairStone+20;
        advanceEconomy(3*cRepairInterval);
        require(lane(1,fLives)==cLives-1 && resource(1, cAttributeStone)==20, "Repairs ignored their cost");
        setLane(1, fLives, cLives); attributes[1][cAttributeStone]=500;
        advanceEconomy(2*cRepairInterval);
        require(lane(1,fLives)==cLives && resource(1, cAttributeStone)==500, "Repairs exceeded the starting lives");
    } else if(test=="life_display") {
        start({2});
        for(int i=0;i<3;++i) units.emplace(sequence++,Unit{waveUnit(0),{float(laneExitX(2)),float(laneY(2)),0}});
        outpostHitpoints[2]=600;
        tick();
        require(units.at(laneLife(2)).hp == 600.0f * (cLives-3) / cLives, "Life display ignored the Outpost's maximum");
        require(mentions("P2 lost 3 lives")==1, "The leak was not reported");
    } else if(test=="tower_access") {
        start({4});
        techStates[{cKeepTech, 4}]=cTechStateDisabled;
        techStates[{cBombardTowerTech, 4}]=cTechStateDisabled;
        advanceTo(sPreparation);
        require(mentions("P4 towers: Watch Tower, Guard Tower; unavailable: Keep, Bombard Tower")==1,
                "Tower access was not explained");
    } else if(test=="shop_walk_across" || test=="shop_walk_rows" || test=="shop_single_file") {
        start({1});
        int pad=cBuyTowerAttack4;
        bool rows = test=="shop_walk_rows";
        int count = test=="shop_single_file" ? 8 : 1;
        float x = rows ? shopX1(pad) + 1.5f : shopX1(pad) - 2.0f;
        float y = rows ? shopY1(pad) - 2.0f : shopY1(pad) + 0.5f;
        for (int offset=0; offset<10; ++offset) {
            bought[1].clear();
            auto ids = kingsAt(1, x + (rows ? 0 : 0.13f * offset), y + (rows ? 0.13f * offset : 0), count, rows ? 0 : 0.6f);
            if (rows) for (std::size_t i=0; i<ids.size(); ++i) units[ids[i]].pos[1] -= 0.6f * i;
            for (int n=0; n<8; ++n) { walk(ids, rows ? 0 : KING_SPEED, rows ? KING_SPEED : 0); tick(); }
            require(bought[1].empty(), "Kings walking across a pad bought it");
            for (int id : ids) units.erase(id);
        }
    } else if(test=="shop_settle") {
        start({1});
        auto ids = kingsAt(1, shopX1(cBuyTowerAttack4) - 2.0f, shopY1(cBuyTowerAttack4) + 0.5f, 1, 0);
        walk(ids, KING_SPEED, 0); tick();
        walk(ids, KING_SPEED, 0); tick();
        walk(ids, KING_SPEED, 0); tick();
        require(bought[1].empty() && kingsOnPad(1, cBuyTowerAttack4)==1, "A King bought while still walking");
        tick(); tick();
        require(bought[1]==std::vector<int>{cBuyTowerAttack4}, "A King that stopped on the pad did not buy");
    } else if(test=="spawn_blocked") {
        start({1});
        int key = cSpawnStride + cBuyBuildingVillagers;
        int blocker = sequence++;
        units.emplace(blocker, Unit{79, {spawnX10(spawnStart(key)) / 10.0f, spawnY10(spawnStart(key)) / 10.0f, 0}, 100, 1});
        kingsOn(1, cBuyBuildingVillagers, 1);
        for(int n=0;n<4;++n) tick();
        require(bought[1].empty() && kingsOnPad(1, cBuyBuildingVillagers)==1, "A blocked spawn took the Kings");
        require(created[1][83]==0, "A blocked purchase left units behind");
        require(told(1, cMessageNoRoom)==1, "The blocked spawn was not explained");
        units.erase(blocker);
        tick(); tick();
        require(bought[1]==std::vector<int>{cBuyBuildingVillagers} && created[1][83]==spawnCount(key), "Cleared spawn did not deliver");
    } else if(test=="transfer") {
        start({2});
        int slot = 2 * cTransferCount;
        int villager = sequence++;
        units.emplace(villager, Unit{293, {transferX1(slot) + 0.5f, transferY1(slot) + 0.5f, 0}, 25, 2});
        int blocker = sequence++;
        units.emplace(blocker, Unit{79, {transferX10(slot) / 10.0f, transferY10(slot) / 10.0f, 0}, 100, 2});
        tick(); tick();
        require(units.count(villager)==1 && created[2][293]==0, "A blocked transfer lost or duplicated the villager");
        units.erase(blocker);
        tick();
        require(units.count(villager)==0 && created[2][293]==1, "The villager was not moved to the other area");
    } else if(test=="king_stall_shared") {
        // Every King walks the shop, so a King standing on another lane's stall cannot hold
        // back that lane's new Kings.
        start({3,5});
        units.emplace(sequence++, Unit{cKing, {laneStallX10(3) / 10.0f, laneStallY10(3) / 10.0f, 0}, 75, 5});
        attributes[3][cAttributeGold]=kingGold(xsTriggerVariable(vDifficulty));
        tick(); tick();
        require(kingsCreated[3]==1 && lane(3,fKings)==0, "A King on the stall held back a new King");
    } else if(test=="shop_civ_lacks") {
        start({5});
        techStates[{cBombardTowerTech, 5}]=cTechStateDisabled;
        kingsOn(5, cBuyBombardAttack400, shopPrice(cBuyBombardAttack400));
        for(int n=0;n<4;++n) tick();
        require(bought[5].empty() && kingsOnPad(5, cBuyBombardAttack400)==shopPrice(cBuyBombardAttack400),
                "A civilization without Bombard Towers paid for their attack");
        require(told(5, cMessageCivilization)==1, "The refusal did not explain the missing towers");
    } else if(test=="age_upgrades") {
        start({1,6});
        techStates[{cGuardTowerTech, 6}]=cTechStateDisabled;
        setLane(1, fOwned, own({cBuyCastleAge}));
        setLane(6, fOwned, own({cBuyCastleAge}));
        tick(); tick();
        auto count=[&](int tech, int player){ return std::count(researched.begin(), researched.end(), std::make_pair(tech, player)); };
        require(count(cGuardTowerTech, 1)==1, "Castle Age did not bring Guard Towers exactly once");
        require(count(cGuardTowerTech, 6)==0, "A civilization without Guard Towers received them");
    } else if(test=="status_display") {
        start({1});
        require(xsTriggerVariable(vDisplayWave)==1, "The first wave is not announced before it starts");
        advanceTo(sWave);
        require(xsTriggerVariable(vDisplayWave)==1 && xsTriggerVariable(vCountdown)==waveDuration(0), "Wave countdown missing");
        tick(true);
        require(xsTriggerVariable(vCountdown)==waveDuration(0)-1, "Wave countdown did not run");
        for(int n=0;n<10000 && phase()==sWave;++n) tick(true);
        require(phase()==sPreparation && xsTriggerVariable(vDisplayWave)==2 && xsTriggerVariable(vCountdown)==cIntermission,
                "The next wave and its countdown were not shown");
    } else if(test=="pending_elimination") {
        start({1,7});
        kingsOn(1, cBuyTowerAttack4, 1);
        for(int n=0;n<cStillSamples;++n) tick();
        ancientTick();
        require(lane(1,fPurchase)==cBuyTowerAttack4, "Purchase not requested");
        setLane(1, fLives, 0);
        ancientTick(); nativeEffects();
        require(lane(1,fActive)==0 && lane(1,fPurchase)==0 && bought[1].empty(), "An eliminated lane's purchase was applied");
    } else if(test=="tower_access_none") {
        start({4});
        for(int tech : {cGuardTowerTech, cKeepTech, cBombardTowerTech}) techStates[{tech, 4}]=cTechStateDisabled;
        advanceTo(sPreparation);
        require(mentions("P4 towers: Watch Tower; unavailable: Guard Tower, Keep, Bombard Tower")==1,
                "A lane without upgrades was not told it keeps Watch Towers");
    } else if(test=="shop_requires_together") {
        // Kings on both age pads at once, or Imperial Kings waiting first: Castle Age always sells first.
        start({1,2});
        kingsOn(1, cBuyImperialAge, 1);
        kingsOn(1, cBuyCastleAge, 1);
        kingsOn(2, cBuyImperialAge, 1);
        for(int n=0;n<6;++n) tick();
        require(bought[1]==std::vector<int>({cBuyCastleAge, cBuyImperialAge}), "Imperial Age was not sold strictly after Castle Age");
        require(bought[2].empty() && kingsOnPad(2, cBuyImperialAge)==1, "Imperial Age was sold without Castle Age");
        kingsOn(2, cBuyCastleAge, 1);
        for(int n=0;n<6;++n) tick();
        require(bought[2]==std::vector<int>({cBuyCastleAge, cBuyImperialAge}), "Castle Age did not unlock the waiting Imperial Age");
    } else if(test=="shop_pause") {
        // A King that stops on a pad for a single sample and walks on has not settled there.
        start({1});
        int pad=cBuyTowerAttack4;
        auto ids = kingsAt(1, shopX1(pad) - 2.0f, shopY1(pad) + 0.5f, 1, 0);
        walk(ids, KING_SPEED, 0); tick();
        walk(ids, KING_SPEED, 0); tick();
        require(kingsOnPad(1, pad)==1, "The King did not reach the pad");
        tick();
        walk(ids, KING_SPEED, 0); tick(); tick();
        require(bought[1].empty(), "A King pausing one sample on a pad bought it");
    } else if(test=="notice_change") {
        start({1});
        kingsOn(1, cBuyLeftAccursedTower, 1);
        for(int n=0;n<4;++n) tick();
        require(bought[1]==std::vector<int>{cBuyLeftAccursedTower}, "The once-only purchase was not made");
        kingsOn(1, cBuyLeftAccursedTower, 1);
        for(int n=0;n<4;++n) tick();
        require(told(1, cMessageOwned)==1, "The first refusal was not explained");
        kingsOn(1, cBuyImperialAge, 1);
        for(int n=0;n<4;++n) tick();
        require(told(1, cMessageRequires)==1, "A different refusal was hidden behind the pause");
        require(toldAnything(1)==2, "Refusals were repeated within the pause");
    } else if(test=="transfer_type") {
        start({2});
        int slot = 2 * cTransferCount;
        units.emplace(sequence++, Unit{293, {transferX1(slot) + 0.5f, transferY1(slot) + 0.5f, 0}, 25, 2});
        tick();
        require(created[2][293]==1 && created[2][83]==0, "The transferred villager changed type");
    } else if(test=="options_default") {
        lobbyDifficulty=4;
        start({3});
        require(xsTriggerVariable(vChooser)==3 && xsTriggerVariable(vMode)==cModeStandard,
                "Solo did not default to a Standard run chosen by its lane");
        require(xsTriggerVariable(vPvp)==0, "A solo run had PvP on");
        require(xsTriggerVariable(vDifficulty)==lobbyLevel(5) && kingGold(xsTriggerVariable(vDifficulty))==1500,
                "Solo did not play the lobby's Easiest setting as Easy");
        require(mentions("Difficulty: Easy")==1, "The difficulty was not announced");
    } else if(test=="options_competitive") {
        lobbyDifficulty=4;
        start({2,5});
        require(xsTriggerVariable(vChooser)==2 && xsTriggerVariable(vPvp)==0,
                "Competition did not default to PvP off, chosen by the first lane");
        require(mentions("P2: PvP is off; select PvP on below the shop before the first wave")==1,
                "The chooser was not invited to switch PvP on");
        require(xsTriggerVariable(vDifficulty)==cCompetitiveLevel, "Competition ignored its fixed difficulty");
    } else if(test=="pvp_opt_in") {
        start({1,7});
        advanceTo(sWave);
        require(xsTriggerVariable(vPvp)==0 && mentions("PvP is off: no raiders or siege in this game.")==1,
                "PvP switched itself on by the first wave");
        kingsOn(1, cBuyLandRaider, 3);
        for(int n=0;n<4;++n) tick(true);
        require(bought[1].empty() && kingsOnPad(1, cBuyLandRaider)==3 && told(1, cMessagePvpOff)==1,
                "A raider was sold without opting into PvP");
    } else if(test=="difficulty_hard") {
        lobbyDifficulty=0;
        start({4});
        require(kingGold(xsTriggerVariable(vDifficulty))==3000, "Hardest did not play Hard");
        attributes[4][cAttributeGold]=2*3000+100;
        tick(); tick();
        require(resource(4, cAttributeGold)==100 && kingsCreated[4]==2, "Hard did not convert 3000 gold per King");
    } else if(test=="difficulty_unknown") {
        lobbyDifficulty=9;
        start({4});
        require(xsTriggerVariable(vDifficulty)==cCompetitiveLevel, "An unknown lobby setting did not play Normal");
    } else if(test=="options_choose") {
        start({3});
        select(3, cControlEndless); tick();
        require(xsTriggerVariable(vMode)==cModeEndless && mentions("P3 chose Endless")==1, "Endless was not chosen");
        tick(); tick();
        require(mentions("P3 chose Endless")==1, "A held selection acted again");
        select(3, 0); tick();
        select(3, cControlPractice); tick();
        require(xsTriggerVariable(vMode)==cModePractice, "Practice was not chosen");
        select(3, cControlStandard); tick();
        require(xsTriggerVariable(vMode)==cModeStandard, "Standard was not chosen back");
    } else if(test=="options_reload_held") {
        start({3});
        select(3, cControlEndless); tick();
        resetXsBuffers(); tick(); tick();
        require(mentions("P3 chose Endless")==1, "A reload repeated a held selection");
    } else if(test=="options_chooser_only") {
        start({2,5});
        auto said = chat.size();
        select(5, cControlPvpOn); tick();
        require(xsTriggerVariable(vPvp)==0 && told(5, cMessageChooserOnly)==1 && chat.size()==said,
                "A lane other than the chooser changed the options, or was told publicly");
        select(2, cControlPvpOn); tick();
        require(xsTriggerVariable(vPvp)==1 && mentions("P2 switched PvP on")==1, "The chooser could not switch PvP on");
        select(2, 0); tick();
        select(2, cControlPvpOff); tick();
        require(xsTriggerVariable(vPvp)==0, "PvP did not switch back off");
    } else if(test=="options_solo_only") {
        start({2,5});
        select(2, cControlEndless); tick();
        require(xsTriggerVariable(vMode)==cModeStandard && told(2, cMessageSoloModes)==1, "Competition chose a solo mode");
    } else if(test=="options_pvp_solo") {
        start({1});
        select(1, cControlPvpOn); tick();
        require(xsTriggerVariable(vPvp)==0 && told(1, cMessageNeedsRivals)==1, "A solo run switched PvP on");
    } else if(test=="options_chooser_leaves") {
        start({2,5,6});
        occupied[2]=false; tick(); tick();
        require(xsTriggerVariable(vChooser)==5, "The run options lost their chooser");
    } else if(test=="options_locked") {
        start({1});
        advanceTo(sWave);
        require(xsTriggerVariable(vLocked)==1, "Options did not lock at the first wave");
        select(1, cControlEndless); tick(true);
        require(xsTriggerVariable(vMode)==cModeStandard && told(1, cMessageOptionsFixed)==1, "Options changed after the first wave");
    } else if(test=="practice_controls") {
        start({6});
        select(6, cControlPractice); tick();
        select(6, cControlKings); tick();
        require(lane(6,fKings)+kingsCreated[6]==cPracticeKings, "Practice did not grant its Kings");
        select(6, cControlResources); tick();
        for(int r : {cAttributeFood, cAttributeWood, cAttributeStone})
            require(resource(6, r)==cPracticeResources, "Practice did not grant its resources");
        // Granted gold converts into Kings as soon as it reaches their price.
        require(resource(6, cAttributeGold)==cPracticeResources % kingGold(xsTriggerVariable(vDifficulty)),
                "Practice did not grant its gold");
        setLane(6, fLives, cLives-5);
        select(6, cControlLives); tick();
        require(lane(6,fLives)==cLives, "Practice did not restore the lives");
        require(xsTriggerVariable(vAssists)==3 && xsTriggerVariable(vLocked)==1, "Assists were not counted or did not fix the run");
        select(6, cControlStandard); tick();
        require(xsTriggerVariable(vMode)==cModePractice, "An assisted run became a Standard run");
    } else if(test=="practice_next_wave") {
        start({6});
        select(6, cControlPractice); tick();
        advanceTo(sPreparation);
        select(6, cControlNextWave); tick(true);
        require(phase()==sWave && xsTriggerVariable(vWave)==0, "Practice did not start the first wave on request");
        require(timerClears==1, "The countdown to the wave kept running after it started");
        select(6, 0); tick(true);
        select(6, cControlNextWave); tick(true);
        require(xsTriggerVariable(vWave)==0 && told(6, cMessagePracticeWave)==1, "A wave started over a running one");
    } else if(test=="practice_refused") {
        start({6});
        select(6, cControlKings); tick();
        require(lane(6,fKings)==0 && kingsCreated[6]==0 && told(6, cMessagePracticeOnly)==1,
                "A practice control worked outside a Practice run");
        require(xsTriggerVariable(vAssists)==0, "A refused control counted as help");
    } else if(test=="results_victory") {
        start({7});
        finishSchedule();
        require(phase()==sVictory, "The solo run was not won");
        require(mentions("Result: Standard run on Normal: 15 waves cleared")==1, "The result did not summarize the run");
        require(xsTriggerVariable(vCleared)==cWaveCount, "The cleared waves were not counted");
    } else if(test=="results_practice") {
        start({7});
        select(7, cControlPractice); tick();
        select(7, cControlLives); tick();
        finishSchedule();
        require(phase()==sVictory && mentions("Result: Practice run on Normal")==1, "The practice result was not shown");
        require(mentions("assisted by 1 practice action")==1, "The result hid the practice help");
    } else if(test=="results_defeat") {
        start({7});
        advanceTo(sWave);
        attributes[8][cAttributeKillsByPlayer1+6]=123;
        setLane(7, fLives, 0); tick(); tick();
        string minutes = ancientCount((xsTriggerVariable(vEconomy) + cSetup) / 60, "game minute", "game minutes");
        require(phase()==sDefeat && mentions("Result: Standard run on Normal: 0 waves cleared, 0 lives left, 123 kills, " + minutes + ".")==1,
                "A defeat did not summarize the run");
    } else if(test=="raider_pvp_off") {
        competitive({1,7}, false);
        kingsOn(1, cBuyLandRaider, 3);
        for(int n=0;n<4;++n) tick(true);
        require(bought[1].empty() && kingsOnPad(1, cBuyLandRaider)==3 && told(1, cMessagePvpOff)==1,
                "A raider was sold with PvP off");
    } else if(test=="raider_before_first_wave") {
        start({1,7});
        kingsOn(1, cBuyNavalRaider, 3);
        for(int n=0;n<4;++n) tick();
        require(bought[1].empty() && told(1, cMessagePvpOff)==1, "A raider was sold before the first wave");
    } else if(test=="raider_solo") {
        start({1}); advanceTo(sWave);
        kingsOn(1, cBuyLandRaider, 3);
        for(int n=0;n<4;++n) tick(true);
        require(bought[1].empty() && kingsOnPad(1, cBuyLandRaider)==3, "A solo run bought a raider");
    } else if(test=="raider_buy") {
        competitive({1,7});
        kingsOn(1, cBuyLandRaider, 3);
        kingsOn(7, cBuyNavalRaider, 3);
        for(int n=0;n<4;++n) tick(true);
        require(bought[1]==std::vector<int>{cBuyLandRaider} && unitsOf(1, 546)==1 && kingsOnPad(1, cBuyLandRaider)==0,
                "The land raider was not bought for its price");
        require(bought[7]==std::vector<int>{cBuyNavalRaider} && unitsOf(7, 1103)==1, "The naval raider was not bought");
    } else if(test=="raider_cap") {
        competitive({1,7});
        for(int round=0; round<3; ++round) { kingsOn(1, cBuyLandRaider, 3); for(int n=0;n<4;++n) tick(true); }
        require(unitsOf(1, 546)==2 && kingsOnPad(1, cBuyLandRaider)==3 && told(1, cMessageRaiderCap)==1,
                "The land raider cap was not kept, or the refused Kings were taken");
        for(auto it=units.begin(); it!=units.end(); ++it) if(it->second.owner==1 && it->second.type==546) { units.erase(it); break; }
        for(int n=0;n<4;++n) tick(true);
        require(unitsOf(1, 546)==2 && kingsOnPad(1, cBuyLandRaider)==0, "A lost raider did not free its place");
    } else if(test=="raider_line") {
        competitive({1,7});
        for(int round=0; round<2; ++round) { kingsOn(1, cBuyNavalRaider, 3); for(int n=0;n<4;++n) tick(true); }
        for(auto &[id, u] : units) if(u.owner==1 && u.type==1103) u.type=529;
        kingsOn(1, cBuyNavalRaider, 3);
        for(int n=0;n<4;++n) tick(true);
        require(unitsOf(1, 1103)==0 && kingsOnPad(1, cBuyNavalRaider)==3, "Upgrading raiders freed their places");
    } else if(test=="raider_civilization") {
        civilizations[1]=100;
        competitive({1,7});
        for(int round=0; round<4; ++round) { kingsOn(1, cBuyLandRaider, 3); for(int n=0;n<4;++n) tick(true); }
        require(unitsOf(1, 546)==3 && kingsOnPad(1, cBuyLandRaider)==3, "The profile's extra land raider was not kept");
        for(int round=0; round<3; ++round) { kingsOn(1, cBuyNavalRaider, 3); for(int n=0;n<4;++n) tick(true); }
        require(unitsOf(1, 1103)==2 && kingsOnPad(1, cBuyNavalRaider)==3, "A land raider bonus reached the naval cap");
    } else if(test=="profile_default") {
        // A civilization no content describes plays the default profile.
        civilizations[3]=200;
        start({3});
        advanceTo(sPreparation);
        require(mentions("P3: default profile: +1 starting King.")==1,
                "The default profile was not announced for an unknown civilization");
        require(kingsCreated[3]==1 && lane(3,fKings)==0, "An unknown civilization did not receive the default King");
        int price = kingGold(xsTriggerVariable(vDifficulty));
        attributes[3][cAttributeGold]=price - 1;
        tick(true);
        require(resource(3, cAttributeGold)==price - 1, "An unknown civilization converted gold below the price");
        attributes[3][cAttributeGold]=price;
        tick(true);
        require(resource(3, cAttributeGold)==0 && lane(3,fKings)+kingsCreated[3]==2, "An unknown civilization did not convert at the full price");
        attributes[8][cAttributeKillsByPlayer1+2]=cKillsPerReward;
        tick(true);
        require(resource(3, cAttributeStone)==cKillStone && resource(3, cAttributeWood)==cKillWood, "An unknown civilization's kill rewards were scaled");
    } else if(test=="profile_kings") {
        civilizations[2]=100;
        start({2});
        require(lane(2,fKings)==2, "Starting Kings were not owed at initialization");
        for(int n=0;n<4;++n) tick();
        require(kingsCreated[2]==2 && lane(2,fKings)==0, "Starting Kings did not arrive at the stall");
        for(int n=0;n<300;++n) tick(true);
        require(kingsCreated[2]==2, "Starting Kings were granted again");
    } else if(test=="profile_gold") {
        civilizations[2]=100;
        start({2});
        int price = kingGold(xsTriggerVariable(vDifficulty)) * 80 / 100;
        attributes[2][cAttributeGold]=price + 10;
        tick(true);
        require(resource(2, cAttributeGold)==10 && told(2, cMessageGold)==1, "The profile's King price was not applied");
        require(mentions("a King per " + ancientText(kingGold(xsTriggerVariable(vDifficulty))) + " gold")==1, "The announced base price changed");
    } else if(test=="profile_kills") {
        civilizations[4]=100;
        start({4});
        attributes[8][cAttributeKillsByPlayer1+3]=cKillsPerReward;
        tick(true);
        require(resource(4, cAttributeStone)==cKillStone * 150 / 100 && resource(4, cAttributeWood)==cKillWood * 150 / 100,
                "Kill rewards were not scaled by the profile");
        // The second reward pays the scaled total less the first, so no rounding is lost.
        attributes[8][cAttributeKillsByPlayer1+3]=2 * cKillsPerReward;
        tick(true);
        require(resource(4, cAttributeStone)==2 * cKillStone * 150 / 100 && resource(4, cAttributeWood)==2 * cKillWood * 150 / 100,
                "Scaled kill rewards lost their rounding across rewards");
    } else if(test=="profile_purchase") {
        // A granted once-only purchase is owned from the start; its units stand where a bought
        // one's would once the lane's setup has run, its tower upgrade follows and it cannot
        // be bought again.
        civilizations[2]=100;
        start({2});
        require(ancientOwns(2, shopMask(cBuyCastleAge)), "The granted purchase was not owned at initialization");
        int castleEntry = spawnStart(2 * cSpawnStride + cBuyCastle);
        require(unitsOf(2, spawnUnit(castleEntry))==0 && lane(2, fProfile)==0,
                "Granted units or the native set arrived before the lane's setup");
        tick();
        bool placed=false;
        for(auto &[id, u] : units)
            if(u.owner==2 && u.type==spawnUnit(castleEntry) && near(u, spawnX10(castleEntry), spawnY10(castleEntry))) placed=true;
        require(placed && unitsOf(2, spawnUnit(castleEntry))==1 && ancientOwns(2, shopMask(cBuyCastle)),
                "The granted castle was not placed on its site after the lane's setup");
        require(unitsOf(3, spawnUnit(castleEntry))==0, "A lane without the grant received a castle");
        require(civNative(100) > 0 && lane(2, fProfile)==civNative(100), "The profile's native set was not requested after setup");
        for(int n=0;n<3;++n) tick();
        require(unitsOf(2, spawnUnit(castleEntry))==1 && lane(2, fProfile)==civNative(100) && lane(3, fProfile)==0,
                "Grants or the native set request repeated or reached another lane");
        bool upgraded=false;
        for(auto &r : researched) if(r.first==cGuardTowerTech && r.second==2) upgraded=true;
        require(upgraded, "The granted age did not bring its tower upgrade");
        kingsOn(2, cBuyCastleAge, 1);
        for(int n=0;n<4;++n) tick();
        require(bought[2].empty() && kingsOnPad(2, cBuyCastleAge)==1 && told(2, cMessageOwned)==1,
                "A granted purchase was sold again");
    } else if(test=="profile_text") {
        civilizations[5]=100; civilizations[6]=101;
        start({5,6});
        advanceTo(sPreparation);
        require(mentions("P5 Testone: +2 starting Kings, Kings cost 20 percent less gold, kill rewards pay 50 percent more stone and wood, Castle Age and Guard Tower from the start, Castle (+20 population) from the start, Bombard Tower attack +400 from the start, +1 land raider with PvP on; a King per " + ancientText(kingGold(xsTriggerVariable(vDifficulty)) * 80 / 100) + " gold.")==1,
                "The civilization line was not announced with the lane's King price");
        require(mentions("P6 Testtwo: no adjustments.")==1, "A neutral profile was not announced");
        require(lane(6, fProfile)==-1, "A neutral profile did not record that it has no native effect set");
    } else if(test=="profile_grant_blocked") {
        // A granted purchase whose spot is blocked is not owned, so it stays on sale.
        civilizations[2]=100;
        int castleEntry = spawnStart(2 * cSpawnStride + cBuyCastle);
        units.emplace(sequence++, Unit{598, {spawnX10(castleEntry) / 10.0f, spawnY10(castleEntry) / 10.0f, 0}, 100, 0});
        start({2});
        tick();
        require(unitsOf(2, spawnUnit(castleEntry))==0, "A castle was placed on a blocked site");
        require(!ancientOwns(2, shopMask(cBuyCastle)) && ancientOwns(2, shopMask(cBuyCastleAge)),
                "A purchase that could not be placed was still owned");
        require(mentions("P2: a starting purchase could not be placed and stays on sale.")==1,
                "The blocked grant was not reported");
    } else if(test=="profile_grant_tree") {
        // A granted purchase for civilizations with a technology this one lacks stays on sale.
        civilizations[2]=100;
        techStates[{cBombardTowerTech, 2}]=cTechStateDisabled;
        start({2});
        tick();
        require(mentions("P2: a starting purchase is not for this civilization and stays on sale.")==1,
                "The grant the civilization cannot use was not reported");
        require(unitsOf(2, spawnUnit(spawnStart(2 * cSpawnStride + cBuyCastle)))==1 && ancientOwns(2, shopMask(cBuyCastle)),
                "The other grants did not go through");
    } else if(test=="siege_price") {
        competitive({1,3,7});
        int price = shopPrice(cBuySiege) + 2 * cSiegeRivalKings;
        kingsOn(1, cBuySiege, price - 1);
        for(int n=0;n<4;++n) tick(true);
        require(bought[1].empty() && xsTriggerVariable(vSiegeOwner)==0, "Siege sold below its price");
        kingsOn(1, cBuySiege, 1);
        for(int n=0;n<4;++n) tick(true);
        require(bought[1]==std::vector<int>{cBuySiege} && kingsOnPad(1, cBuySiege)==0 && xsTriggerVariable(vSiegeOwner)==1,
                "Siege did not cost its base price plus each surviving rival's share");
    } else if(test=="siege_exclusive") {
        competitive({1,7});
        int price = shopPrice(cBuySiege) + cSiegeRivalKings;
        kingsOn(1, cBuySiege, price);
        kingsOn(7, cBuySiege, price);
        for(int n=0;n<4;++n) tick(true);
        require(bought[1].size() + bought[7].size()==1, "Two players held the siege at once");
        int loser = bought[1].empty() ? 1 : 7;
        require(kingsOnPad(loser, cBuySiege)==price && told(loser, cMessageSiegeHeld)==1, "The competing purchase lost its Kings");
    } else if(test=="siege_timeline") {
        competitive({1,3,7});
        int price = shopPrice(cBuySiege) + 2 * cSiegeRivalKings;
        kingsOn(1, cBuySiege, price);
        for(int n=0;n<3;++n) tick(true);
        require(xsTriggerVariable(vSiegeOwner)==1 && xsTriggerVariable(vSiegePhase)==1, "The siege warning did not start");
        for(int n=0;n<cSiegeWarning;++n) tick(true);
        require(xsTriggerVariable(vSiegePhase)==2 && unitsOf(1, 42)==2 * cSiegeTrebuchets, "Trebuchets did not arrive near every rival");
        for(auto &[id, u] : units) if(u.owner==1 && u.type==42) {
            bool near3 = std::abs(u.pos[1] - siegeY10(3 * 3) / 10.0f) < 0.6f, near7 = std::abs(u.pos[1] - siegeY10(7 * 3) / 10.0f) < 0.6f;
            require(near3 || near7, "A trebuchet was placed away from the rivals' islets");
        }
        for(auto &[id, u] : units) if(u.owner==1 && u.type==42) { u.type=331; break; }
        for(int n=0;n<cSiegeActive;++n) tick(true);
        require(xsTriggerVariable(vSiegeOwner)==0 && unitsOf(1, 42)==0 && unitsOf(1, 331)==0, "Expiry left siege behind");
        require(xsTriggerVariable(vSiegeCooldown)==cSiegeSharedCooldown && lane(1, fSiegeCooldown)==cSiegeBuyerCooldown,
                "Expiry did not start both cooldowns");
        kingsOn(7, cBuySiege, price);
        for(int n=0;n<4;++n) tick(true);
        require(bought[7].empty() && told(7, cMessageSiegeCooldown)==1, "The siege sold during its cooldown");
        for(int n=0;n<cSiegeSharedCooldown;++n) tick(true);
        require(bought[7]==std::vector<int>{cBuySiege}, "Another player could not buy after the shared cooldown");
    } else if(test=="siege_buyer_waits") {
        competitive({1,7});
        int price = shopPrice(cBuySiege) + cSiegeRivalKings;
        kingsOn(1, cBuySiege, price);
        for(int n=0;n<4+cSiegeWarning+cSiegeActive+cSiegeSharedCooldown;++n) tick(true);
        require(xsTriggerVariable(vSiegeCooldown)==0 && lane(1, fSiegeCooldown)>0, "The buyer's cooldown is not longer");
        kingsOn(1, cBuySiege, price);
        for(int n=0;n<4;++n) tick(true);
        require(bought[1].size()==1 && kingsOnPad(1, cBuySiege)==price, "The buyer skipped its own cooldown");
    } else if(test=="siege_owner_eliminated") {
        competitive({1,3,7});
        int price = shopPrice(cBuySiege) + 2 * cSiegeRivalKings;
        kingsOn(1, cBuySiege, price);
        for(int n=0;n<3;++n) tick(true);
        setLane(1, fLives, 0);
        for(int n=0;n<cSiegeWarning+2;++n) tick(true);
        require(xsTriggerVariable(vSiegeOwner)==0 && unitsOf(1, 42)==0, "An eliminated owner's siege went ahead");
        require(xsTriggerVariable(vSiegeCooldown)>0, "Ending the siege did not start the cooldown");
    } else if(test=="siege_resume") {
        competitive({1,7});
        int price = shopPrice(cBuySiege) + cSiegeRivalKings;
        kingsOn(1, cBuySiege, price);
        for(int n=0;n<3+cSiegeWarning+5;++n) tick(true);
        auto saved=variables; auto savedUnits=units; auto savedBought=bought;
        for(int n=0;n<cSiegeActive+5;++n) tick(true);
        auto expected=variables; auto expectedUnits=units.size();
        variables=saved; units=savedUnits; bought=savedBought;
        resetXsBuffers();
        for(int n=0;n<cSiegeActive+5;++n) tick(true);
        require(variables==expected && units.size()==expectedUnits, "Reload changed the siege's ownership, timing or units");
    } else if(test=="siege_tie") {
        // Claims made in the same second go to the lane the rotating order reaches first,
        // never always to the lower slot.
        competitive({1,7});
        int price = shopPrice(cBuySiege) + cSiegeRivalKings;
        // The purchase lands on the third clock after the Kings arrive; make that clock put P7 first.
        auto before=[](int clock){
            for(int turn=0;turn<7;++turn) {
                if(ancientTurn(clock, turn)==7) return true;
                if(ancientTurn(clock, turn)==1) return false;
            }
            return false;
        };
        for(int n=0;n<20 && !before(xsTriggerVariable(vEconomy) + 3);++n) tick(true);
        kingsOn(1, cBuySiege, price);
        kingsOn(7, cBuySiege, price);
        for(int n=0;n<3;++n) tick(true);
        require(xsTriggerVariable(vSiegeOwner)==7 && bought[1].empty(), "The lower slot won a tie it should have lost");
    } else if(test=="kill_rewards_waves_only") {
        // Raiders taking rival traders and raiders kill nothing of the enemy's, so pay nothing.
        competitive({4,7});
        attributes[4][cAttributeKills]=5*cKillsPerReward;
        tick(true); tick(true);
        require(resource(4, cAttributeStone)==0, "Kills of rival units paid a reward");
        attributes[8][cAttributeKillsByPlayer1+3]=cKillsPerReward;
        tick(true);
        require(resource(4, cAttributeStone)==cKillStone && resource(7, cAttributeStone)==0,
                "Wave kills did not pay their killer alone");
    } else if(test=="siege_holder_again") {
        competitive({1,7});
        int price = shopPrice(cBuySiege) + cSiegeRivalKings;
        kingsOn(1, cBuySiege, price);
        for(int n=0;n<4;++n) tick(true);
        require(xsTriggerVariable(vSiegeOwner)==1, "The siege was not bought");
        kingsOn(1, cBuySiege, price);
        for(int n=0;n<4;++n) tick(true);
        require(kingsOnPad(1, cBuySiege)==price && told(1, cMessageSiegeYours)==1 && told(1, cMessageSiegeHeld)==0,
                "The holder was told that another player holds the siege");
    } else if(test=="sudden_labels") {
        start({1,7});
        reachWave(cWaveCount + 1);
        require(mentions("Sudden death wave 1 (wave 16)")==1 && mentions("Next: sudden death wave 2 (wave 17)")==1,
                "Sudden death waves were not announced as such");
        require(mentions("ndless wave")==0, "Sudden death waves were announced as Endless");
    } else if(test=="practice_repeat") {
        // Each new selection acts once, even when the same control is selected again soon after.
        start({6});
        select(6, cControlPractice); tick();
        select(6, cControlKings); tick();
        require(lane(6, fControl)==0, "A handled selection stayed pending");
        tick();
        select(6, cControlKings); tick();
        require(lane(6,fKings)+kingsCreated[6]==2*cPracticeKings && xsTriggerVariable(vAssists)==2,
                "Selecting a control again did not act again");
    } else if(test=="shared_arrivals") {
        // Rival units parked on a lane's raider and trader arrival spots block nothing.
        competitive({1,7});
        for(int purchase : {cBuyLandRaider, cBuyTradeCarts}) {
            int key = cSpawnStride + purchase;
            for(int e = spawnStart(key); e < spawnStart(key) + spawnCount(key); ++e)
                units.emplace(sequence++, Unit{546, {spawnX10(e) / 10.0f, spawnY10(e) / 10.0f, 0}, 100, 7});
            kingsOn(1, purchase, shopPrice(purchase));
            for(int n=0;n<4;++n) tick(true);
        }
        require(bought[1]==std::vector<int>({cBuyLandRaider, cBuyTradeCarts}) && unitsOf(1, 546)==1
                && created[1][128]==spawnCount(cSpawnStride + cBuyTradeCarts), "A rival unit blocked an arrival");
        require(told(1, cMessageNoRoom)==0, "A shared arrival was refused for lack of room");
    } else if(test=="economy_towers") {
        // Towers belong in the build rows: one in the resource area is removed, wherever it stands.
        start({2});
        int inside = sequence++;
        units.emplace(inside, Unit{236, {laneEconomyX2(2) + 0.5f, laneEconomyY1(2) + 0.5f, 0}, 100, 2});
        int corner = sequence++;
        units.emplace(corner, Unit{79, {laneEconomyX1(2) + 0.5f, laneEconomyY2(2) + 0.5f, 0}, 100, 2});
        int row = sequence++;
        units.emplace(row, Unit{235, {30.5f, float(laneY(2)) - 3.5f, 0}, 100, 2});
        int life = laneLife(2);
        tick(); tick();
        require(units.count(inside)==0 && units.count(corner)==0, "A tower stayed in the resource area");
        require(units.count(row)==1 && units.count(life)==1, "A tower or Outpost outside the resource area was removed");
        require(told(2, cMessageEconomyTower)==1, "The removal was not explained once");
    } else if(test=="turns_fair") {
        // Over fourteen seconds every lane goes first against every other exactly seven times.
        for(int a=1;a<=7;++a) for(int b=a+1;b<=7;++b) {
            int first=0;
            for(int clock=0;clock<14;++clock) {
                std::vector<int> order;
                for(int turn=0;turn<7;++turn) order.push_back(ancientTurn(clock, turn));
                std::vector<int> sorted=order; std::sort(sorted.begin(), sorted.end());
                require(sorted==std::vector<int>({1,2,3,4,5,6,7}), "A second skipped or repeated a lane");
                if(std::find(order.begin(), order.end(), a) < std::find(order.begin(), order.end(), b)) ++first;
            }
            require(first==7, "A pair of lanes did not share going first");
        }
    } else require(false,"Unknown case");
}
