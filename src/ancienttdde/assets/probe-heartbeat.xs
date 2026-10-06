rule ancientProbeHeartbeat
active
minInterval 1
{
    int ticks = xsTriggerVariable(0) + 1;
    xsSetTriggerVariable(0, ticks);
    if (ticks % 10 == 0) {
        xsChatData("Embedded XS heartbeat: %d", ticks);
    }
}
