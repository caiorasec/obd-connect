"""OBD Connect protocol constants."""

DOMAIN = "obd_connect"
MAX_RECORDS = 256
MAX_BODY = 262144
FRESH_MS = 180000
METRICS = {
    "010C": ("Engine RPM", "rpm", 0, 16384),
    "010D": ("Vehicle speed", "km/h", 0, 255),
    "0105": ("Coolant temperature", "°C", -40, 215),
    "0104": ("Engine load", "%", 0, 100),
    "0111": ("Throttle", "%", 0, 100),
    "010B": ("Intake pressure", "kPa", 0, 255),
    "010F": ("Intake temperature", "°C", -40, 215),
    "0142": ("Control module voltage", "V", 0, 66),
    "ATRV": ("Adapter voltage", "V", 0, 100),
}
