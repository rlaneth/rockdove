import os
from dotenv import load_dotenv

load_dotenv()

# APRS-IS configuration
CALLSIGN = os.getenv("CALLSIGN", "NOCALL")
PASSWORD = os.getenv("APRS_PASSWORD", "00000")
SERVER = os.getenv("APRS_SERVER", "rotate.aprs2.net")
PORT = int(os.getenv("APRS_PORT", "14580"))

# API configuration
API_URL = os.getenv("METAR_API_URL", "")

# Station configuration
OBJECT_LAT = os.getenv("OBJECT_LAT", "-22.910")
OBJECT_LON = os.getenv("OBJECT_LON", "-43.163")
OBJECT_ID = os.getenv("OBJECT_ID", "SBRJ")

# Packet data
DATA_COMMENT = os.getenv("DATA_COMMENT", "")
