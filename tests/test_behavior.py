from ancienttdde.inspection.behavior import extract_purchases, extract_waves


def component(kind, **attributes):
    return {"type": kind, "attributes": attributes}


def trigger(identifier, name, *, conditions=(), effects=(), enabled=0, looping=0):
    return {
        "id": identifier,
        "name": name,
        "enabled": enabled,
        "looping": looping,
        "conditions": list(conditions),
        "effects": list(effects),
    }


def test_wave_timing_follows_activation_ids_instead_of_mislabelled_stop_names():
    rows = [
        trigger(
            10,
            "Start lvl 9-B",
            conditions=[component("timer", timer=45)],
            effects=[
                component("activate_trigger", trigger_id=11),
                component("activate_trigger", trigger_id=12),
            ],
            enabled=1,
        ),
        trigger(
            11,
            "lvl 9-B",
            conditions=[component("timer", timer=3)],
            looping=1,
            effects=[
                component(
                    "create_object",
                    source_player=8,
                    object_list_unit_id=777,
                    location_x=8,
                    location_y=14,
                )
            ],
        ),
        trigger(
            12,
            "Stop lvl 8-B",
            conditions=[component("timer", timer=45)],
            effects=[
                component("deactivate_trigger", trigger_id=11),
                component("activate_trigger", trigger_id=13),
            ],
        ),
        trigger(
            13,
            "Start lvl 9-C",
            conditions=[component("timer", timer=45)],
            effects=[
                component("activate_trigger", trigger_id=14),
                component("activate_trigger", trigger_id=15),
            ],
        ),
        trigger(
            14,
            "lvl 9-C",
            conditions=[component("timer", timer=3)],
            looping=1,
            effects=[
                component(
                    "create_object",
                    source_player=8,
                    object_list_unit_id=680,
                    location_x=8,
                    location_y=14,
                )
            ],
        ),
        trigger(
            15,
            "Stop lvl 9-C",
            conditions=[component("timer", timer=45)],
            effects=[component("deactivate_trigger", trigger_id=14)],
        ),
    ]
    first, second = extract_waves(rows)
    assert first.start_seconds == 45
    assert first.stop_trigger_id == 12
    assert first.duration_seconds == 45
    assert second.start_seconds == 135
    assert first.spawns[0]["object_id"] == 777


def test_boss_is_single_spawn_and_preserves_healing_and_timer_victory():
    rows = [
        trigger(
            1000,
            "Boss 1",
            conditions=[component("timer", timer=60)],
            enabled=1,
            effects=[
                component(
                    "create_object",
                    source_player=8,
                    object_list_unit_id=1777,
                    location_x=8,
                    location_y=15,
                ),
                component("damage_object", quantity=-5999945, source_player=8),
                component("activate_trigger", trigger_id=1010),
            ],
        ),
        trigger(
            1010,
            "WIN",
            conditions=[component("timer", timer=70)],
            effects=[component("declare_victory", source_player=1, enabled=1)],
        ),
    ]
    (wave,) = extract_waves(rows)
    assert wave.kind == "boss"
    assert wave.interval_seconds is None
    assert wave.start_seconds == 60
    assert wave.modifications[0]["attributes"]["quantity"] == -5999945


def test_purchase_preserves_excess_payment_region_and_linked_income():
    purchase = trigger(
        49,
        "Buy income",
        enabled=1,
        looping=1,
        conditions=[
            component(
                "objects_in_area",
                quantity=3,
                source_player=2,
                object_group=59,
                area_x1=1,
                area_y1=2,
                area_x2=3,
                area_y2=4,
            )
        ],
        effects=[
            component(
                "remove_object",
                source_player=2,
                object_group=59,
                area_x1=0,
                area_y1=2,
                area_x2=3,
                area_y2=4,
            ),
            component("activate_trigger", trigger_id=50),
        ],
    )
    income = trigger(
        50,
        "Income",
        looping=1,
        conditions=[component("timer", timer=120)],
        effects=[
            component("tribute", source_player=0, target_player=2, tribute_list=3, quantity=450)
        ],
    )
    (result,) = extract_purchases([purchase, income], {49})
    assert result.required_kings == 3
    assert result.player_id == 2
    assert result.payment_policy == "all_matching_objects_in_removal_regions"
    assert result.condition_region != result.removal_regions[0]
    assert result.linked_triggers == (income,)


def test_unfiltered_villager_shop_condition_is_not_silently_corrected():
    row = trigger(
        287,
        "Building Villager",
        conditions=[
            component(
                "objects_in_area",
                quantity=1,
                source_player=1,
                area_x1=139,
                area_y1=46,
                area_x2=140,
                area_y2=49,
            )
        ],
        effects=[component("remove_object", source_player=1, object_group=59)],
    )
    (result,) = extract_purchases([row], {287})
    assert result.condition_object_group is None


def test_unreachable_wave_has_no_invented_absolute_start():
    row = trigger(
        1,
        "lvl 1-A",
        looping=1,
        conditions=[component("timer", timer=3)],
        effects=[
            component(
                "create_object",
                source_player=8,
                object_list_unit_id=83,
                location_x=8,
                location_y=14,
            )
        ],
    )
    (result,) = extract_waves([row])
    assert result.start_seconds is None
