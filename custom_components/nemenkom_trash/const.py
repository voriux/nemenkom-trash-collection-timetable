DOMAIN = "nemenkom_trash"

CONF_STREET = "street"
CONF_UPDATE_INTERVAL_HOURS = "update_interval_hours"

DEFAULT_STREET = "Vaikystės g."
DEFAULT_UPDATE_INTERVAL_HOURS = 168  # 7 days

WASTE_TYPES = ("packaging", "glass", "household")

WASTE_TYPE_LABELS = {
    "packaging": "Packaging (Paper/Plastic/Metal)",
    "glass": "Glass",
    "household": "Household Waste",
}

WASTE_TYPE_ICONS = {
    "packaging": "mdi:recycle",
    "glass": "mdi:bottle-wine",
    "household": "mdi:trash-can",
}
