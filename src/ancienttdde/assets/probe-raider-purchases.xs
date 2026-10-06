int ancientRaiderPaymentIds = -1;

void ancientPurchaseRaider(int player = 1, int objectId = -1, int kingId = -1,
    int cap = 2, int x1 = 0, int y1 = 0, int x2 = 0, int y2 = 0,
    float spawnX = 0.0, float spawnY = 0.0, string kindName = "")
{
    // Check the current count during execution, rather than relying on a trigger gate.
    int living = xsGetObjectCount(player, objectId);
    if (living < 0 || living >= cap) {
        return;
    }
    ancientRaiderPaymentIds = xsGetPlayerUnitIds(player, kingId, ancientRaiderPaymentIds);
    int first = -1;
    int second = -1;
    int third = -1;
    int index = 0;
    while (index < xsArrayGetSize(ancientRaiderPaymentIds) && third < 0) {
        int unitId = xsArrayGetInt(ancientRaiderPaymentIds, index);
        vector position = xsGetUnitPosition(unitId);
        float x = xsVectorGetX(position);
        float y = xsVectorGetY(position);
        if (xsGetUnitHitpoints(unitId) > 0 && xsGetGarrisonedInUnitId(unitId) < 0
            && x >= x1 && x < x2 && y >= y1 && y < y2) {
            if (first < 0) {
                first = unitId;
            } else if (second < 0) {
                second = unitId;
            } else {
                third = unitId;
            }
        }
        index = index + 1;
    }
    if (third < 0) {
        return;
    }

    // A blocked or otherwise failed creation leaves every payment King untouched.
    int created = xsCreateUnit(objectId, player, xsVectorSet(spawnX, spawnY, 0.0), false, true, true);
    if (created < 0) {
        return;
    }
    xsRemoveUnit(first);
    xsRemoveUnit(second);
    xsRemoveUnit(third);
    xsChatData(kindName + " raider purchased: 3 Kings.");
}
