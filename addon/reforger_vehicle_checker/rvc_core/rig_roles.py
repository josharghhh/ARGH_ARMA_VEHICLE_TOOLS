from __future__ import annotations

import re


SAMPLECAR_PARENT = {
    "v_root": None,
    "v_body": "v_root",
    "v_axle_01": "v_body",
    "v_axle_02": "v_body",
    "v_suspension_l01": "v_axle_01",
    "v_suspension_r01": "v_axle_01",
    "v_suspension_l02": "v_axle_02",
    "v_suspension_r02": "v_axle_02",
    "v_rotator_l01": "v_suspension_l01",
    "v_rotator_r01": "v_suspension_r01",
    "v_rotator_l02": "v_suspension_l02",
    "v_rotator_r02": "v_suspension_r02",
    "v_wheel_l01": "v_rotator_l01",
    "v_wheel_r01": "v_rotator_r01",
    "v_wheel_l02": "v_suspension_l02",
    "v_wheel_r02": "v_suspension_r02",
    "v_door_l01": "v_body",
    "v_door_r01": "v_body",
    "v_door_l02": "v_body",
    "v_door_r02": "v_body",
    "v_trunk": "v_body",
    "v_steering_wheel": "v_body",
    "v_pedal_brake": "v_body",
    "v_pedal_throttle": "v_body",
    "v_handbrake": "v_body",
}

ROLE_SLOT_BONES = {
    "WHEEL": {
        "FL": "v_wheel_l01",
        "FR": "v_wheel_r01",
        "RL": "v_wheel_l02",
        "RR": "v_wheel_r02",
    },
    "ROTATOR": {
        "FL": "v_rotator_l01",
        "FR": "v_rotator_r01",
        "RL": "v_rotator_l02",
        "RR": "v_rotator_r02",
    },
    "SUSPENSION": {
        "FL": "v_suspension_l01",
        "FR": "v_suspension_r01",
        "RL": "v_suspension_l02",
        "RR": "v_suspension_r02",
    },
    "DOOR": {
        "FL": "v_door_l01",
        "FR": "v_door_r01",
        "RL": "v_door_l02",
        "RR": "v_door_r02",
        "TRUNK": "v_trunk",
    },
}


def normalize_name(name: str) -> str:
    return re.sub(r"[\s_.\-]+", "", (name or "").lower())


def tokenized_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def is_steering_name(name: str) -> bool:
    text = normalize_name(name)
    return (
        text in {"steeringwheel", "vsteeringwheel", "steerwheel", "steerwheel0"}
        or "steeringwheel" in text
        or "steerwheel" in text
        or ("steering" in text and "wheel" in text)
    )


def infer_slot(name: str, default: str = "FL") -> str:
    text = tokenized_name(name)
    norm = normalize_name(name)
    if any(token in text.split("_") for token in ("trunk", "boot", "tailgate", "hatch")):
        return "TRUNK"
    compact = norm[1:] if norm.startswith("v") else norm
    for prefix in ("wheelrotator", "suspension", "rotator", "wheel", "wheels", "rotor", "tyre", "tire", "door"):
        if not compact.startswith(prefix):
            continue
        tail = compact[len(prefix):]
        if tail.startswith(("rr", "rearright", "r02")):
            return "RR"
        if tail.startswith(("rl", "rearleft", "l02")):
            return "RL"
        if tail.startswith(("fr", "frontright", "r01")):
            return "FR"
        if tail.startswith(("fl", "frontleft", "l01")):
            return "FL"
        if tail.startswith(("right", "r")):
            return "FR"
        if tail.startswith(("left", "l")):
            return "FL"
    if re.search(r"(^|_)r(ear)?_?r(ight)?($|_)", text) or "rr" in text.split("_") or "r02" in norm:
        return "RR"
    if re.search(r"(^|_)r(ear)?_?l(eft)?($|_)", text) or "rl" in text.split("_") or "l02" in norm:
        return "RL"
    if re.search(r"(^|_)f(ront)?_?r(ight)?($|_)", text) or "fr" in text.split("_") or "r01" in norm:
        return "FR"
    if re.search(r"(^|_)f(ront)?_?l(eft)?($|_)", text) or "fl" in text.split("_") or "l01" in norm:
        return "FL"
    if "right" in text.split("_") or re.search(r"(^|_)r($|_)", text):
        return "FR"
    if "left" in text.split("_") or re.search(r"(^|_)l($|_)", text):
        return "FL"
    if norm.endswith("right"):
        return "FR"
    if norm.endswith("left"):
        return "FL"
    return default


def resolve_role_from_name(name: str) -> tuple[str, str]:
    norm = normalize_name(name)
    if is_steering_name(name):
        return "STEERING", ""
    if "rotator" in norm or "wheelrotator" in norm or "rotor" in norm:
        return "ROTATOR", infer_slot(name)
    if "suspension" in norm or "spring" in norm or "damper" in norm or "shock" in norm:
        return "SUSPENSION", infer_slot(name)
    if "door" in norm or any(token in norm for token in ("trunk", "tailgate", "hatch")):
        return "DOOR", infer_slot(name)
    if (
        any(token in norm for token in ("tyre", "tire"))
        or re.search(r"(^|_)wheel($|_|\d)", tokenized_name(name))
        or norm.startswith(("wheelfl", "wheelfr", "wheelrl", "wheelrr"))
        or norm in {"wheel", "wheels"}
    ):
        return "WHEEL", infer_slot(name)
    if "handbrake" in norm or "parkingbrake" in norm:
        return "HANDBRAKE", ""
    if "pedalbrake" in norm or "brakepedal" in norm:
        return "PEDAL_BRAKE", ""
    if "pedalaccelerator" in norm or "acceleratorpedal" in norm or "pedalthrottle" in norm:
        return "PEDAL_THROTTLE", ""
    if "interior" in norm or "seat" in norm or "dashboard" in norm or "console" in norm:
        return "INTERIOR", ""
    return "BODY", ""


def target_bone_for_role(role: str, slot: str = "", custom_bone: str = "") -> str:
    role = (role or "").upper()
    slot = (slot or "").upper()
    if role == "CUSTOM":
        return custom_bone
    if role == "STEERING":
        return "v_steering_wheel"
    if role == "HANDBRAKE":
        return "v_handbrake"
    if role == "PEDAL_BRAKE":
        return "v_pedal_brake"
    if role == "PEDAL_THROTTLE":
        return "v_pedal_throttle"
    if role in {"BODY", "INTERIOR", "LIGHT", "GLASS"}:
        return "v_body"
    if role in ROLE_SLOT_BONES:
        return ROLE_SLOT_BONES[role].get(slot or "FL", "")
    return ""


def resolve_target_bone(
    name: str,
    manual_role: str = "",
    manual_slot: str = "",
    manual_target: str = "",
) -> tuple[str, str, str]:
    if manual_target:
        return manual_role or "CUSTOM", manual_slot, manual_target
    if manual_role:
        slot = manual_slot or infer_slot(name)
        return manual_role, slot, target_bone_for_role(manual_role, slot, manual_target)
    role, slot = resolve_role_from_name(name)
    return role, slot, target_bone_for_role(role, slot)


def opposite_bone_name(name: str) -> str:
    swaps = (
        ("_l01", "_r01"), ("_r01", "_l01"),
        ("_l02", "_r02"), ("_r02", "_l02"),
        ("_FL", "_FR"), ("_FR", "_FL"),
        ("_RL", "_RR"), ("_RR", "_RL"),
        ("_left", "_right"), ("_right", "_left"),
        ("left", "right"), ("right", "left"),
    )
    for left, right in swaps:
        if left in name:
            return name.replace(left, right, 1)
    return ""


def is_road_wheel_name(name: str) -> bool:
    text = tokenized_name(name)
    norm = normalize_name(name)
    if is_steering_name(name):
        return False
    role, _slot = resolve_role_from_name(name)
    if role in {"ROTATOR", "SUSPENSION", "STEERING"}:
        return False
    if role == "WHEEL":
        return True
    if any(token in norm for token in ("wheelarch", "wheelwell", "wheelhouse")):
        return False
    tokens = set(text.split("_"))
    return bool(
        tokens & {"wheel", "wheels", "tire", "tires", "tyre", "tyres"}
        or norm.startswith(("wheelfl", "wheelfr", "wheelrl", "wheelrr"))
    )
