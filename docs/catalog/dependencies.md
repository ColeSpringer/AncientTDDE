# Mod dependency migration inventory

Every supplied graphics file is dropped from the modern gameplay package.
Retained semantics use stock appearances, generated text and scenario-local
logic. Candidate carriers are explicit in `content/migration/objects.json`.

| Original asset | DAT graphics | Audited object IDs | Replacement |
| --- | --- | --- | --- |
| b_100ap_x1.smx | [12434] | [1744] | Generated shop text/objectives and stock display markers |
| b_10ap_x1.smx | [12431] | [1741] | Generated shop text/objectives and stock display markers |
| b_1500stone_x1.smx | [12447] | [1757] | Generated shop text/objectives and stock display markers |
| b_170ap_x1.smx | [12435] | [1745] | Generated shop text/objectives and stock display markers |
| b_175gold2_x1.smx | [12456] | [1766] | Generated shop text/objectives and stock display markers |
| b_1ap30s_x1.smx | [12440] | [1750] | Generated shop text/objectives and stock display markers |
| b_1apper5_x1.smx | [12457] | [1767] | Generated shop text/objectives and stock display markers |
| b_1kgold2_x1.smx | [12454] | [1764] | Generated shop text/objectives and stock display markers |
| b_1kingper1_x1.smx | [12452] | [1762] | Generated shop text/objectives and stock display markers |
| b_1kingper2_x1.smx | [12449] | [1759] | Generated shop text/objectives and stock display markers |
| b_20relics_x1.smx | [12438] | [1748] | Generated shop text/objectives and stock display markers |
| b_255ap_x1.smx | [12436] | [1746] | Generated shop text/objectives and stock display markers |
| b_25ap_x1.smx | [12432] | [1742] | Generated shop text/objectives and stock display markers |
| b_2kwood_x1.smx | [12451] | [1761] | Generated shop text/objectives and stock display markers |
| b_375stone_x1.smx | [12445] | [1755] | Generated shop text/objectives and stock display markers |
| b_3ap30s_x1.smx | [12439] | [1749] | Generated shop text/objectives and stock display markers |
| b_3carts_x1.smx | [12453] | [1763] | Generated shop text/objectives and stock display markers |
| b_3cogs_x1.smx | [12459] | [1769] | Generated shop text/objectives and stock display markers |
| b_3rdtower_x1.smx | [12462] | [1772] | Generated shop text/objectives and stock display markers |
| b_3relic_x1.smx | [12458] | [1768] | Generated shop text/objectives and stock display markers |
| b_450gold2_x1.smx | [12455] | [1765] | Generated shop text/objectives and stock display markers |
| b_4ap_x1.smx | [12430] | [1740] | Generated shop text/objectives and stock display markers |
| b_4thtower_x1.smx | [12461] | [1771] | Generated shop text/objectives and stock display markers |
| b_50ap_x1.smx | [12433] | [1743] | Generated shop text/objectives and stock display markers |
| b_750ap_x1.smx | [12437] | [1747] | Generated shop text/objectives and stock display markers |
| b_800stone_x1.smx | [12442] | [1752] | Generated shop text/objectives and stock display markers |
| b_80pop_x1.smx | [12450] | [1760] | Generated shop text/objectives and stock display markers |
| b_balrogId_x1.smx | [12475] | [1780] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_balrogwa_x1.smx | [12476] | [1780] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_bossflame_x1.smx | [12479] | [1783] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_buildingvill_x1.smx | [12446] | [1756] | Generated shop text/objectives and stock display markers |
| b_castleage_x1.smx | [12441] | [1751] | Generated shop text/objectives and stock display markers |
| b_castlestore_x1.smx | [12463] | [1773] | Generated shop text/objectives and stock display markers |
| b_cavetrollwalk_x1.smx | [12473, 12474] | [1779] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_cavtroll idle_x1.smx | [] | [] | No audited object dependency; drop unused bitmap from modern package |
| b_cursedreskin_x1.smx | [12426] | [684] | Stock Accursed Tower appearance and explicit local stats/life display |
| b_cursedreskindestro_x1.smx | [12427] | [684] | Stock Accursed Tower appearance and explicit local stats/life display |
| b_cursedreskinrubble_x1.smx | [12425] | [684] | Stock Accursed Tower appearance and explicit local stats/life display |
| b_deathstar2_x1.smx | [12428] | [1786] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_discord_x1.smx | [12429] | [] | No audited object dependency; drop unused bitmap from modern package |
| b_dragonid_x1.smx | [12469] | [1781] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_dragonwa_x1.smx | [12470] | [1781] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_entidle_x1.smx | [12477] | [1782] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_entwalk_x1.smx | [12478] | [1782] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_foodbonus_x1.smx | [12465] | [1775] | Generated shop text/objectives and stock display markers |
| b_goldbonus_x1.smx | [12466] | [1776] | Generated shop text/objectives and stock display markers |
| b_impage_x1.smx | [12443] | [1753] | Generated shop text/objectives and stock display markers |
| b_lraccursed_x1.smx | [12444] | [1754] | Generated shop text/objectives and stock display markers |
| b_nazgulknightid_x1.smx | [12480] | [1784] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_nazgulknightwa_x1.smx | [12481] | [1784] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_repvill_x1.smx | [12460] | [1770] | Generated shop text/objectives and stock display markers |
| b_resvill_x1.smx | [12448] | [1758] | Generated shop text/objectives and stock display markers |
| b_sauronid_x1.smx | [12467] | [1777] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_sauronwa_x1.smx | [12468] | [1777] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_spideridle_x1.smx | [12482] | [1785] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_spiderwalk_x1.smx | [12483] | [1785] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |
| b_stonebonus_x1.smx | [12464] | [1774] | Generated shop text/objectives and stock display markers |
| b_tyran_idleA_x1.smx | [12471] | [] | No audited object dependency; drop unused bitmap from modern package |
| b_tyran_walk_x1.smx | [12472] | [1778] | Stock boss carriers with scenario-local stats; prototype candidate in objects.json |

## ID collisions and role mappings

Gaia 1738 is a gold deposit and Gaia 1739 is a stone deposit; these numeric IDs
represent unrelated units in modern DE. Candidates are gold mine 66 and stone
mine 102. The same legacy IDs in human/enemy DAT tables are empty definitions
and are explicitly dropped in those contexts. Gaia 1740–1776 are price and
instruction signs with custom bitmaps; corresponding human definitions are
empty. Bosses 1777–1786 are custom living units whose modern IDs include
decorative or unrelated stock objects, so they are replaced with explicit stock
boss carriers (Champion as an initial prototype candidate). Special towers and
life meters both use 684, and require separate named instance roles.

The current parser dataset supplies stock candidate names; it does not prove
behavior or rendering in a current game build. Legacy map terrain IDs also
require verification in milestone 2. The legacy scenario remains unchanged, and
all selected object definitions and graphic chains are available in `dat.json`.
