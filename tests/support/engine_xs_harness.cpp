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
constexpr int cTechStateDisabled = -1;
constexpr int cTechStateDone = 3;
constexpr int cHitpoints = 0;
constexpr int cVillagerClass = 904;
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
        case 598: return 3;                               // Outpost
        case 83: case 293: return 4;                      // Villager
        case 125: return 18;                              // Monk
        case 128: return 19;                              // Trade Cart
        case 601: return 30;                              // Flag
        case 79: return 52;                               // Watch Tower
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
// Native triggers acknowledge one request per lane each pass, as the generated ones do.
void nativeEffects() {
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
                    if (u.owner == p && (u.type == 83 || u.type == 128 || u.type == 17) && near(u, spawnX10(entry), spawnY10(entry)))
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
        start({1,7}); advanceTo(sSuddenDeath);
        int lives=lane(1,fLives); for(int n=0;n<cSuddenInterval;++n) tick(true);
        require(lane(1,fLives)<lives && lane(1,fLives)==lane(7,fLives), "Sudden death pressure is asymmetric");
        advanceTo(sDefeat); require(xsTriggerVariable(vWinner)==8, "Tied sudden death favored a slot");
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
        attributes[3][cAttributeGold]=2*cKingGold+600;
        tick();
        require(resource(3, cAttributeGold)==600, "Gold was not converted in whole Kings");
        require(told(3, cMessageGold)==1 && mentions("gold")==0, "The conversion was not told to its player alone");
        tick();
        require(kingsCreated[3]==2 && lane(3,fKings)==0, "Converted Kings did not arrive");
    } else if(test=="kill_rewards") {
        start({4});
        attributes[4][cAttributeKills]=cKillsPerReward-1;
        tick(); require(resource(4, cAttributeStone)==0, "A reward came early");
        attributes[4][cAttributeKills]=cKillsPerReward;
        tick();
        require(resource(4, cAttributeStone)==cKillStone && resource(4, cAttributeWood)==cKillWood, "Kill reward wrong");
        attributes[4][cAttributeKills]=cKillsPerReward*cRewardsPerKing;
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
        start({1});
        setLane(1, fOwned, own({cBuyGold1000, cBuyKingEveryMinute}));
        for(int n=0;n<cSetup;++n) tick(true);
        require(xsTriggerVariable(vEconomy)<=1 && kingsCreated[1]==0, "Investments paid during setup");
        advanceEconomy(240-xsTriggerVariable(vEconomy));
        tick(true);
        require(resource(1, cAttributeGold)==2000, "Gold investment did not pay every two minutes");
        require(kingsCreated[1]==4, "King investment did not pay every minute");
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
    } else if(test=="king_stall_blocked") {
        start({3});
        int blocker = sequence++;
        units.emplace(blocker, Unit{79, {laneStallX10(3) / 10.0f, laneStallY10(3) / 10.0f, 0}, 100, 3});
        attributes[3][cAttributeGold]=cKingGold;
        tick(); tick();
        require(kingsCreated[3]==0 && lane(3,fKings)==1, "A King was lost to a blocked stall");
        units.erase(blocker);
        tick();
        require(kingsCreated[3]==1 && lane(3,fKings)==0, "The waiting King did not arrive");
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
    } else require(false,"Unknown case");
}
