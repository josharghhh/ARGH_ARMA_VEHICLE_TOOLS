from __future__ import annotations

import re


COLLIDER_PREFIXES = ("UCX_", "UBX_", "UCL_", "UTM_", "USP_", "UCS_")
MASTER_EXCLUDED_ROLES = {"door", "glass", "light", "wheel"}
MASTER_ALLOWED_COLLIDER_PREFIXES = (
    "UCX_MainCol_",
    "UBX_MainCol_",
    "UCL_MT_wheel_",
    "UCX_FG_",
    "UTM_FG_Body",
    "UTM_FG_Exterior",
    "UTM_FG_Interior",
    "UTM_FG_Door",
    "UTM_FG_Trunk",
)


_WHEEL_BODY_GUARD = (
    "arch", "well", "house", "fender", "guard", "mudflap", "flare", "skirt"
)
_GLASS_RE = re.compile(
    r"(?:^|[_.\s])(?:glass|window|windows|windshield|windscreen|windscreen|"
    r"windscreen|windshield|reflectorglass|chromereflector)(?:$|[_.\s\d])",
    re.IGNORECASE,
)
_LIGHT_RE = re.compile(
    r"(?:^|[_.\s])(?:headlight|brakelight|taillight|tail_light|light|lights|"
    r"lamp|lamps|indicator|blinker|reverselight|foglight|spotlight|spot|"
    r"lightbar|dome|domelight|siren|strobe|flasher|beacon|pursuit|bulb|led|"
    r"leds|reflector)(?:$|[_.\s\d])",
    re.IGNORECASE,
)
_WHEEL_RE = re.compile(
    r"(?:^|[_.\s])(?:wheel|wheels|tire|tires|tyre|tyres|rim|rims|rimcap|"
    r"rimcaps|hubcap|hubcaps|hub)(?:$|[_.\s\d])",
    re.IGNORECASE,
)
_DOOR_RE = re.compile(
    r"(?:^|[_.\s])(?:door|doors|trunk|boot|hatch|tailgate|decklid)(?:$|[_.\s\d])",
    re.IGNORECASE,
)


def clean_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return token or "Object"


def semantic_text(name: str, collections: tuple[str, ...] = ()) -> str:
    text = " ".join((name, *collections))
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return f"_{text.lower()}_"


def is_collider_name(name: str) -> bool:
    return name.startswith(COLLIDER_PREFIXES)


def classify_object_name(name: str, collections: tuple[str, ...] = ()) -> str:
    text = semantic_text(name, collections)
    if is_collider_name(name):
        return "collider"
    if _GLASS_RE.search(text):
        return "glass"
    if _LIGHT_RE.search(text):
        return "light"
    if _WHEEL_RE.search(text) and not any(guard in text for guard in _WHEEL_BODY_GUARD):
        if "steering" not in text:
            return "wheel"
    if _DOOR_RE.search(text):
        return "door"
    return "body"


def collider_profile(name: str) -> str:
    if name.startswith(("UCL_VC_wheel", "UTM_FG_Wheel")):
        return "wheel"
    if name.startswith(("UTM_Glass", "UTM_GlassFire")):
        return "glass"
    if name.startswith(("UTM_FG_Light", "UCX_FG_Light")):
        return "light"
    if name.startswith(MASTER_ALLOWED_COLLIDER_PREFIXES):
        return "master"
    if name.startswith("UTM_VC_") and "wheel" not in name.lower():
        return "forbidden_master_vehiclecomplex"
    return "other"


def include_in_master(name: str, collections: tuple[str, ...] = ()) -> bool:
    role = classify_object_name(name, collections)
    if role == "collider":
        return collider_profile(name) == "master"
    return role not in MASTER_EXCLUDED_ROLES


def include_in_profile(
    profile: str, name: str, collections: tuple[str, ...] = ()
) -> bool:
    role = classify_object_name(name, collections)
    if profile == "master":
        return include_in_master(name, collections)
    if role == "collider":
        return collider_profile(name) == profile
    return role == profile


def slot_from_name(name: str) -> str:
    text = semantic_text(name)
    for slot, patterns in {
        "FL": ("_fl_", "_front_left_", "_l01_"),
        "FR": ("_fr_", "_front_right_", "_r01_"),
        "RL": ("_rl_", "_rear_left_", "_l02_"),
        "RR": ("_rr_", "_rear_right_", "_r02_"),
        "F": ("_f_", "_front_", "_windscreen_", "_windshield_"),
        "R": ("_r_", "_rear_", "_back_", "_trunk_", "_tailgate_"),
    }.items():
        if any(pattern in text for pattern in patterns):
            return slot
    return clean_token(name)


def profile_filename(asset_name: str, profile: str, slot: str | None = None) -> str:
    asset = clean_token(asset_name)
    if profile == "master":
        return f"{asset}.fbx"
    label = {"glass": "Glass", "light": "Light", "wheel": "Wheel"}[profile]
    suffix = clean_token(slot or profile)
    return f"{asset}_{label}_{suffix}.fbx"
