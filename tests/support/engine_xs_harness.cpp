// Only DE API boundaries are substituted; the generated XS drives every transition.
#include <array>
#include <cstdlib>
#include <iostream>
#include <map>
#include <string>
#include <vector>
using string = std::string;
using vector = std::array<float, 3>;
struct Unit { int type; vector pos; float hp = 100; int owner = 8; };
std::map<int, Unit> units;
std::array<int, 256> variables{};
std::array<bool, 9> occupied{};
constexpr int cPlayerTypeHuman = 1;
constexpr int cPlayerTypeComputer = 3;
constexpr int cArcherClass = 900;
constexpr int cSentinelEndClass = 965;
std::array<int, 9> playerTypes{};
std::vector<std::vector<int>> arrays;
int sequence = 1;
int xsTriggerVariable(int id) { return variables.at(id); }
void xsSetTriggerVariable(int id, int value) { variables.at(id) = value; }
bool xsGetPlayerInGame(int player) { return occupied.at(player); }
int xsGetPlayerType(int player) { return playerTypes.at(player); }
// Stock classes of the defense-player objects used below. DE addresses class N as 900 + N.
int classOf(int type) {
    switch (type) {
        case 17: return 2;                                // Trade Cog
        case 68: case 129: case 130: case 131: return 3;  // Mill and its age forms
        case 293: return 4;                               // Villager
        case 128: return 19;                              // Trade Cart
        case 601: return 30;                              // Flag
        case 79: return 52;                               // Watch Tower
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
int xsArrayGetSize(int id) { return arrays.at(id).size(); }
int xsArrayGetInt(int id, int index) { return arrays.at(id).at(index); }
float xsGetUnitHitpoints(int id) { return units.at(id).hp; }
vector xsGetUnitPosition(int id) { return units.at(id).pos; }
float xsVectorGetX(vector pos) { return pos[0]; }
float xsVectorGetY(vector pos) { return pos[1]; }
bool xsRemoveUnit(int id) { return units.erase(id) == 1; }
void xsChatData(string, int = 0) {}
// EMBEDDED_XS
void require(bool ok, string message) { if (!ok) { std::cerr << message << '\n'; std::exit(1); } }
int lane(int player, int field) { return xsTriggerVariable(laneVariable(player, field)); }
void setLane(int player, int field, int value) { xsSetTriggerVariable(laneVariable(player, field), value); }
int phase() { return xsTriggerVariable(vPhase); }
std::array<int, 9> grants{}, income{}, spawns{}, cleanups{};
std::array<int, 9> berryMills{};
void nativeEffects() {
    for (int p=1; p<=7; ++p) {
        if (lane(p, fActive) && !lane(p, fInitialized)) { ++grants[p]; setLane(p, fInitialized, 1); }
        if (lane(p, fCleanup)) {
            ancientCleanupLane(p, berryMills[p]);
            ++cleanups[p]; setLane(p, fCleanup, 0);
        }
        if (lane(p, fActive) && lane(p, fIncome)) { ++income[p]; setLane(p, fIncome, 0); }
        int wave = lane(p, fSpawn) - 1;
        if (lane(p, fActive) && wave >= 0) {
            spawns[p] += waveCount(wave);
            for (int i=0; i<waveCount(wave); ++i)
                units.emplace(sequence++, Unit{waveUnit(wave), {float(laneSpawnX(p)), float(laneY(p)), 0}});
            setLane(p, fSpawn, 0);
        }
    }
}
void tick(bool clear=false) { if (clear) units.clear(); ancientTick(); nativeEffects(); }
void start(std::initializer_list<int> humans) {
    occupied.fill(true);
    playerTypes.fill(cPlayerTypeComputer);
    for (int p:humans) playerTypes[p]=cPlayerTypeHuman;
    tick();
}
void advanceTo(int desired) {
    for(int n=0; n<10000 && phase()!=desired; ++n) tick(true);
    require(phase()==desired, "Expected state was not reached");
}
int main(int argc, char** argv) {
    require(argc == 2, "Need case"); string test=argv[1];
    if(test=="berry_mills") {
        // Each lane owns a mill plus one object from every other class it starts with.
        std::array<std::vector<int>, 9> laneUnits{};
        for(int p=1;p<=7;++p) {
            berryMills[p]=sequence;
            units.emplace(sequence++, Unit{68, {84, float(laneY(p)), 0}, 100, p});
            for(int type: {293, 79, 128, 17, 601}) {
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
        }
        units.at(berryMills[2]).type=131;
        int extraMill=sequence++;
        units.emplace(extraMill, Unit{68, {80, float(laneY(2)), 0}, 100, 2});
        arrays.clear(); ancientUnitArray=-1;
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
            require(!grants[p] && !income[p] && !spawns[p], "AI filler was paid or spawned");
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
        start({2,7}); int paid=income[2];
        if(test=="resign") occupied[2]=false; else setLane(2,fLives,0);
        tick(); tick();
        require(phase()==sVictory && xsTriggerVariable(vWinner)==7, "Last survivor did not win");
        for(int n=0;n<30;++n) tick();
        require(income[2]==paid && lane(2,fActive)==0, "Eliminated lane still receives income");
    } else if(test=="sudden") {
        start({1,7}); advanceTo(sSuddenDeath);
        int lives=lane(1,fLives); for(int n=0;n<cSuddenInterval;++n) tick(true);
        require(lane(1,fLives)<lives && lane(1,fLives)==lane(7,fLives), "Sudden death pressure is asymmetric");
        advanceTo(sDefeat); require(xsTriggerVariable(vWinner)==8, "Tied sudden death favored a slot");
    } else if(test=="resume") {
        start({2,7}); advanceTo(sWave); for(int n=0;n<27;++n) tick(true);
        auto saved=variables; auto savedUnits=units; auto savedIncome=income; auto savedSpawns=spawns;
        for(int n=0;n<35;++n) tick(true);
        auto expected=variables; auto expectedIncome=income; auto expectedSpawns=spawns;
        variables=saved; units=savedUnits; income=savedIncome; spawns=savedSpawns;
        arrays.clear(); ancientUnitArray=-1;
        for(int n=0;n<35;++n) tick(true);
        require(variables==expected && income==expectedIncome && spawns==expectedSpawns, "Reload changed progress/timers");
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
        tick(); require(lane(2,fLives)==cLives-4 && lane(7,fLives)==cLives-4 && units.empty(), "Leaks were not counted exactly once");
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
        tick(); require(lane(2,fLives)==cLives-1 && lane(7,fLives)==cLives-1 && units.empty(),
                        "An enemy that stopped at the exit was not counted as a leak");
    } else require(false,"Unknown case");
}
