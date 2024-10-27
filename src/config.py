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
STATION_LAT = os.getenv("STATION_LAT", "-22.910")
STATION_LON = os.getenv("STATION_LON", "-43.163")
STATION_ID = os.getenv("STATION_ID", "SBRJ")

# Packet data
OBJECT_NAME = os.getenv("OBJECT_NAME", "SBRJ-METAR")
DATA_COMMENT = os.getenv("DATA_COMMENT", "")
