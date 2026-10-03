#include <genie/dat/DatFile.h>

#include <cstdlib>
#include <exception>
#include <iostream>

genie::DatFile g_dat;

// Expose the top-level DAT sections directly to GDB. This avoids relying on
// GDB's member lookup for genie::DatFile itself.
decltype(g_dat.FileVersion)* g_FileVersion = nullptr;
decltype(g_dat.FloatPtrTerrainTables)* g_FloatPtrTerrainTables = nullptr;
decltype(g_dat.TerrainPassGraphicPointers)* g_TerrainPassGraphicPointers = nullptr;
decltype(g_dat.TerrainRestrictions)* g_TerrainRestrictions = nullptr;
decltype(g_dat.PlayerColours)* g_PlayerColours = nullptr;
decltype(g_dat.Sounds)* g_Sounds = nullptr;
decltype(g_dat.GraphicPointers)* g_GraphicPointers = nullptr;
decltype(g_dat.Graphics)* g_Graphics = nullptr;
decltype(g_dat.TerrainBlock)* g_TerrainBlock = nullptr;
decltype(g_dat.RandomMaps)* g_RandomMaps = nullptr;
decltype(g_dat.Effects)* g_Effects = nullptr;
decltype(g_dat.UnitHeaders)* g_UnitHeaders = nullptr;
decltype(g_dat.Civs)* g_Civs = nullptr;
decltype(g_dat.Techs)* g_Techs = nullptr;
decltype(g_dat.UnitLines)* g_UnitLines = nullptr;
decltype(g_dat.TechTree)* g_TechTree = nullptr;
decltype(g_dat.TimeSlice)* g_TimeSlice = nullptr;
decltype(g_dat.UnitKillRate)* g_UnitKillRate = nullptr;
decltype(g_dat.UnitKillTotal)* g_UnitKillTotal = nullptr;
decltype(g_dat.UnitHitPointRate)* g_UnitHitPointRate = nullptr;
decltype(g_dat.UnitHitPointTotal)* g_UnitHitPointTotal = nullptr;
decltype(g_dat.RazingKillRate)* g_RazingKillRate = nullptr;
decltype(g_dat.RazingKillTotal)* g_RazingKillTotal = nullptr;
decltype(g_dat.TerrainsUsed1)* g_TerrainsUsed1 = nullptr;
decltype(g_dat.SUnknown2)* g_SUnknown2 = nullptr;
decltype(g_dat.SUnknown3)* g_SUnknown3 = nullptr;
decltype(g_dat.swgbBlendModes)* g_swgbBlendModes = nullptr;
decltype(g_dat.swgbMaxBlendmodes)* g_swgbMaxBlendmodes = nullptr;
decltype(g_dat.SUnknown7)* g_SUnknown7 = nullptr;
decltype(g_dat.SUnknown8)* g_SUnknown8 = nullptr;

extern "C" __attribute__((noinline)) void dat_dump_breakpoint()
{
#if defined(__GNUC__)
    asm volatile("" ::: "memory");
#endif
}

static void expose_members()
{
    g_FileVersion = &g_dat.FileVersion;
    g_FloatPtrTerrainTables = &g_dat.FloatPtrTerrainTables;
    g_TerrainPassGraphicPointers = &g_dat.TerrainPassGraphicPointers;
    g_TerrainRestrictions = &g_dat.TerrainRestrictions;
    g_PlayerColours = &g_dat.PlayerColours;
    g_Sounds = &g_dat.Sounds;
    g_GraphicPointers = &g_dat.GraphicPointers;
    g_Graphics = &g_dat.Graphics;
    g_TerrainBlock = &g_dat.TerrainBlock;
    g_RandomMaps = &g_dat.RandomMaps;
    g_Effects = &g_dat.Effects;
    g_UnitHeaders = &g_dat.UnitHeaders;
    g_Civs = &g_dat.Civs;
    g_Techs = &g_dat.Techs;
    g_UnitLines = &g_dat.UnitLines;
    g_TechTree = &g_dat.TechTree;
    g_TimeSlice = &g_dat.TimeSlice;
    g_UnitKillRate = &g_dat.UnitKillRate;
    g_UnitKillTotal = &g_dat.UnitKillTotal;
    g_UnitHitPointRate = &g_dat.UnitHitPointRate;
    g_UnitHitPointTotal = &g_dat.UnitHitPointTotal;
    g_RazingKillRate = &g_dat.RazingKillRate;
    g_RazingKillTotal = &g_dat.RazingKillTotal;
    g_TerrainsUsed1 = &g_dat.TerrainsUsed1;
    g_SUnknown2 = &g_dat.SUnknown2;
    g_SUnknown3 = &g_dat.SUnknown3;
    g_swgbBlendModes = &g_dat.swgbBlendModes;
    g_swgbMaxBlendmodes = &g_dat.swgbMaxBlendmodes;
    g_SUnknown7 = &g_dat.SUnknown7;
    g_SUnknown8 = &g_dat.SUnknown8;
}

int main()
{
    const char* input = std::getenv("DAT_INPUT");
    if (!input || !*input) {
        std::cerr << "DAT_INPUT is not set\n";
        return 1;
    }

    try {
        g_dat.setGameVersion(genie::GV_C17);
        g_dat.load(input);
        expose_members();

        std::cerr
            << "Loaded " << input << "\n"
            << "File version: " << g_dat.FileVersion << "\n"
            << "Civilizations: " << g_dat.Civs.size() << "\n"
            << "Graphics: " << g_dat.Graphics.size() << "\n"
            << "Sounds: " << g_dat.Sounds.size() << "\n"
            << "Effects: " << g_dat.Effects.size() << "\n"
            << "Technologies: " << g_dat.Techs.size() << "\n"
            << "Unit headers: " << g_dat.UnitHeaders.size() << "\n";

        dat_dump_breakpoint();
        return 0;
    }
    catch (const std::exception& e) {
        std::cerr << "Failed to load DAT: " << e.what() << "\n";
        return 2;
    }
}
