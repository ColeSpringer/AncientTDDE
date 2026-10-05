// DE itself is unavailable here. Supply only the XS API contracts used by purchases;
// the embedded transaction and its serialized effect calls run without translation.
#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <map>
#include <string>
#include <vector>

using vector = std::array<float, 3>;
using string = std::string;
struct Unit { int owner; int type; vector position; float hp = 100; int garrison = -1; };
std::map<int, Unit> units;
std::vector<std::vector<int>> arrays;
int nextId = 0;
int messages = 0;

vector xsVectorSet(float x, float y, float z) { return {x, y, z}; }
float xsVectorGetX(vector position) { return position[0]; }
float xsVectorGetY(vector position) { return position[1]; }
vector xsGetUnitPosition(int id) { return units.at(id).position; }
float xsGetUnitHitpoints(int id) { return units.at(id).hp; }
int xsGetGarrisonedInUnitId(int id) { return units.at(id).garrison; }
int xsArrayGetSize(int array) { return static_cast<int>(arrays.at(array).size()); }
int xsArrayGetInt(int array, int index) { return arrays.at(array).at(index); }
int xsGetObjectCount(int player, int type) {
    int count = 0;
    for (auto &[id, unit] : units)
        if (unit.owner == player && unit.type == type && unit.hp > 0) ++count;
    return count;
}
int xsGetPlayerUnitIds(int player, int type, int array = -1) {
    if (array < 0) { array = static_cast<int>(arrays.size()); arrays.emplace_back(); }
    arrays.at(array).clear();
    for (auto &[id, unit] : units)
        if (unit.owner == player && unit.type == type) arrays.at(array).push_back(id);
    return array;
}
int addUnit(int player, int type, vector position) {
    int id = nextId++;
    units.emplace(id, Unit{player, type, position});
    return id;
}
int xsCreateUnit(int type, int player, vector position,
                 bool /*foundation*/ = false, bool /*playSound*/ = true, bool collision = true) {
    if (collision)
        for (auto &[id, unit] : units)
            if (unit.hp > 0 && unit.garrison < 0 &&
                std::abs(unit.position[0] - position[0]) < 1 &&
                std::abs(unit.position[1] - position[1]) < 1) return -1;
    return addUnit(player, type, position);
}
bool xsRemoveUnit(int id) { return units.erase(id) == 1; }
void xsChatData(string) { ++messages; }
void removeNativePayment(int player, int type, int quantity, int x1, int y1, int x2, int y2) {
    for (auto it = units.begin(); it != units.end() && quantity > 0;) {
        Unit &unit = it->second;
        if (unit.owner == player && unit.type == type && unit.hp > 0 && unit.garrison < 0 &&
            unit.position[0] >= x1 && unit.position[0] < x2 + 1 &&
            unit.position[1] >= y1 && unit.position[1] < y2 + 1) {
            it = units.erase(it); --quantity;
        } else { ++it; }
    }
}

// EMBEDDED_XS
// PURCHASE_FUNCTIONS

void buyLand() {
    // LAND_PURCHASE
}
void buyNaval() {
    // NAVAL_PURCHASE
}

void require(bool holds, const char *message) {
    if (!holds) { std::cerr << message << '\n'; std::exit(1); }
}

int main(int argc, char **argv) {
    require(argc == 3, "Expected a test case and raider kind");
    string test = argv[1];
    bool naval = string(argv[2]) == "naval";
    int type = naval ? 539 : 448;
    int padX = naval ? 18 : 8;
    vector spawn = xsVectorSet(18.5, naval ? 50.5 : 16.5, 0);
    auto buy = naval ? buyNaval : buyLand;
    auto kings = [&](int count) {
        for (int i = 0; i < count; ++i) addUnit(1, 434, xsVectorSet(padX + 0.5, 27.5, 0));
    };
    auto moveRaiders = [&]() {
        for (auto &[id, unit] : units)
            if (unit.owner == 1 && unit.type == type) unit.position[0] = 30 + id * 2;
    };
    if (test == "blocked") {
        kings(6); buy(); buy();
        require(xsGetObjectCount(1, type) == 1, "A blocked spawn must not create a raider");
        require(xsGetObjectCount(1, 434) == 3, "A blocked spawn consumed payment");
        require(messages == 1, "A blocked spawn announced a successful purchase");
        moveRaiders(); buy();
        require(xsGetObjectCount(1, type) == 2, "Clearing the spawn did not allow purchase");
        require(xsGetObjectCount(1, 434) == 0, "Successful retry did not charge exactly 3 Kings");
    } else if (test == "cap") {
        addUnit(1, type, xsVectorSet(32, spawn[1], 0));
        addUnit(1, type, xsVectorSet(36, spawn[1], 0));
        kings(6); buy(); moveRaiders(); buy();
        require(xsGetObjectCount(1, type) == 2, "Purchase exceeded the living cap of 2");
        require(xsGetObjectCount(1, 434) == 6, "A purchase at the cap consumed Kings");
        require(messages == 0, "A purchase at the cap announced success");
    } else if (test == "payment") {
        kings(2);
        for (int i = 0; i < 3; ++i) addUnit(8, 434, xsVectorSet(padX + 0.5, 27.5, 0));
        buy();
        require(xsGetObjectCount(1, type) == 0, "Insufficient owner payment created a raider");
        require(xsGetObjectCount(1, 434) == 2, "Insufficient payment consumed Kings");
        kings(1); buy();
        require(xsGetObjectCount(1, type) == 1, "Three owner Kings did not purchase a raider");
        require(xsGetObjectCount(1, 434) == 0 && xsGetObjectCount(8, 434) == 3,
                "Purchase removed the wrong player's Kings");
    } else if (test == "excess") {
        kings(4); buy(); moveRaiders(); kings(3); buy();
        require(xsGetObjectCount(1, type) == 2 && xsGetObjectCount(1, 434) == 1,
                "Purchases did not charge exactly 3 Kings each");
        moveRaiders(); kings(3); buy();
        require(xsGetObjectCount(1, type) == 2 && xsGetObjectCount(1, 434) == 4,
                "Repeated purchase exceeded the cap or consumed payment");
    } else if (test == "replacement") {
        int dead = addUnit(1, type, xsVectorSet(32, spawn[1], 0));
        addUnit(1, type, xsVectorSet(36, spawn[1], 0));
        addUnit(8, type, xsVectorSet(42, spawn[1], 0));
        kings(3); buy();
        require(xsGetObjectCount(1, 434) == 3, "Buying at the living cap charged Kings");
        units.at(dead).hp = 0; buy();
        require(xsGetObjectCount(1, type) == 2 && xsGetObjectCount(1, 434) == 0,
                "A dead raider or rival raider prevented replacement");
    } else if (test == "scope") {
        addUnit(1, 434, xsVectorSet(padX + 6, 27.5, 0));
        addUnit(1, 434, xsVectorSet(padX + 0.5, 32, 0));
        int garrisoned = addUnit(1, 434, xsVectorSet(padX + 0.5, 27.5, 0));
        units.at(garrisoned).garrison = 100;
        buy();
        require(xsGetObjectCount(1, type) == 0 && xsGetObjectCount(1, 434) == 3,
                "Out-of-pad or garrisoned Kings were accepted as payment");
        for (int i = 0; i < 3; ++i) addUnit(1, 434, xsVectorSet(padX + 5.9, 31.9, 0));
        buy();
        require(xsGetObjectCount(1, type) == 1 && xsGetObjectCount(1, 434) == 3,
                "Payment did not respect the inclusive pad tiles");
    } else { require(false, "Unknown test case"); }
    for (auto &[id, unit] : units)
        if (unit.owner == 1 && unit.type == type && unit.position[0] == spawn[0])
            require(unit.position == spawn, "Raider was created outside its designated spawn");
}
