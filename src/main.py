from config import *
from metar import Metar
from typing import Optional
import logging
import requests
import socket
from math import exp

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - Rockdove - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Rockdove")


def calculate_humidity(temp_c: float, dewpoint_c: float) -> int:
    """Calculate relative humidity from temperature and dewpoint (in Celsius)"""
    # Magnus formula constants
    b = 17.625
    c = 243.04

    # Calculate vapor pressure and saturation vapor pressure
    gamma_t = (b * temp_c) / (c + temp_c)
    gamma_d = (b * dewpoint_c) / (c + dewpoint_c)

    # Calculate relative humidity
    rh = 100 * exp(gamma_d - gamma_t)

    return int(round(rh))


def parse_metar(metar_string: str) -> Optional[Metar.Metar]:
    """Parse METAR string into Metar object"""
    if not metar_string:
        return None

    # Clean up METAR string
    metar_string = (
        metar_string[6:] if metar_string.startswith("METAR ") else metar_string
    )
    metar_string = metar_string[:-1] if metar_string.endswith("=") else metar_string

    try:
        return Metar.Metar(metar_string)
    except Exception as e:
        logger.error(f"Error parsing METAR: {e}")
        return None


def decimal_to_ddmmss(decimal_degrees: float, is_latitude: bool = True) -> str:
    """Convert decimal degrees to DDMM.SS format"""
    absolute = abs(decimal_degrees)
    degrees = int(absolute)
    minutes = (absolute - degrees) * 60

    if is_latitude:
        direction = "S" if decimal_degrees < 0 else "N"
        return f"{degrees:02d}{minutes:05.2f}{direction}"

    direction = "W" if decimal_degrees < 0 else "E"
    return f"{degrees:03d}{minutes:05.2f}{direction}"


# Store API response globally to avoid multiple calls
_api_response = None


def get_api_data() -> Optional[dict]:
    """Fetch and cache API response"""
    global _api_response
    if _api_response is None:
        try:
            response = requests.get(API_URL)
            response.raise_for_status()
            _api_response = response.json()
        except Exception as e:
            logger.error(f"Error fetching API data: {e}")
            return None
    return _api_response


def fetch_metar() -> Optional[str]:
    """Fetch METAR data from the API endpoint"""
    data = get_api_data()
    if data and data.get("status") and "data" in data:
        return data["data"]["metar"]
    return None


def get_visibility_conditions() -> str:
    """Get visibility conditions from the API response"""
    data = get_api_data()
    if data and data.get("status") and "data" in data:
        return data["data"]["visibilidade"]
    return "NA"


def get_sky_conditions() -> str:
    """Get sky conditions from the API response"""
    data = get_api_data()
    if data and data.get("status") and "data" in data:
        return data["data"]["ceu"]
    return "NA"


def get_weather_conditions() -> str:
    """Get weather conditions from the API response"""
    data = get_api_data()
    if data and data.get("status") and "data" in data:
        return data["data"]["condicoes_tempo"]
    return "NA"


def format_aprs_weather(obs: Optional[Metar.Metar]) -> Optional[str]:
    """Convert METAR data to APRS weather format"""
    if not obs:
        return None

    try:
        # Format position
        lat = float(STATION_LAT)
        lon = float(STATION_LON)
        position = f"{decimal_to_ddmmss(lat)}/{decimal_to_ddmmss(lon, False)}"

        # Convert weather values
        wind_speed_mph = int(obs.wind_speed.value() * 1.15078) if obs.wind_speed else 0
        temp_f = int(obs.temp.value() * 1.8 + 32) if obs.temp else 0
        pressure = int(obs.press.value() * 10) if obs.press else 0
        wind_dir = int(obs.wind_dir.value()) if obs.wind_dir else 0

        # Calculate humidity from temperature and dewpoint
        humidity = (
            calculate_humidity(obs.temp.value(), obs.dewpt.value())
            if obs.temp and obs.dewpt
            else 0
        )

        # Format the weather packet
        weather_data = (
            f"@"  # Use @ for weather reports with timestamp
            f"{obs.time.strftime('%d%H%M')}z"  # Add zulu timestamp
            f"{position}"
            f"_{wind_dir:03d}/{wind_speed_mph:03d}"  # Weather data format
            f"g..."  # Wind gust
            f"t{temp_f:03d}"
            f"r..."  # Rain last hour
            f"p..."  # Rain last 24 hours
            f"h{humidity:02d}"
            f"b{pressure:05d}"
        )

        return weather_data

    except Exception as e:
        logger.error(f"Error formatting weather data: {e}")
        return None


def send_to_aprs(weather_packet: str) -> bool:
    """Send position and weather data to APRS-IS"""
    if not weather_packet:
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)

    try:
        sock.connect((SERVER, PORT))
        sock.recv(1024)  # Read banner

        login = f"user {CALLSIGN} pass {PASSWORD} vers Rockdove 0.1\n"
        sock.send(login.encode())

        response = sock.recv(1024).decode().strip()
        if "unverified" in response.lower():
            logger.error("APRS-IS login failed")
            return False

        # Get additional conditions
        visibility_conditions = get_visibility_conditions()
        sky_conditions = get_sky_conditions()
        weather_conditions = get_weather_conditions()

        # Send weather data packet
        weather_packet = f"{STATION_ID}>RKDV,TCPIP*:{weather_packet}\n"
        sock.send(weather_packet.encode())
        logger.info(f"Sent weather packet: {weather_packet.strip()}")

        # Send position packet with airport symbol
        lat = float(STATION_LAT)
        lon = float(STATION_LON)
        position = f"{decimal_to_ddmmss(lat)}/{decimal_to_ddmmss(lon, False)}"
        ad = (
            f"Visib {visibility_conditions} Ceu {sky_conditions} "
            f"- {weather_conditions} - {DATA_COMMENT}"
        )

        position_packet = f"{STATION_ID}>RKDV,TCPIP*:={position}^{ad}\n"
        sock.send(position_packet.encode())
        logger.info(f"Sent position packet: {position_packet.strip()}")

        return True

    except Exception as e:
        logger.error(f"Error sending to APRS-IS: {e}")
        return False
    finally:
        sock.close()


def main() -> int:
    """Main function that runs once and exits"""
    logger.info("Rockdove starting")

    try:
        # Reset API response cache
        global _api_response
        _api_response = None

        # Fetch and process METAR data
        metar_string = fetch_metar()
        if not metar_string:
            logger.error("Failed to fetch METAR data")
            return 1

        # Clean up METAR string if needed
        metar_string = (
            metar_string[6:] if metar_string.startswith("METAR ") else metar_string
        )

        obs = parse_metar(metar_string)
        if not obs:
            logger.error("Failed to parse METAR data")
            return 1

        weather_packet = format_aprs_weather(obs)
        if not weather_packet:
            logger.error("Failed to format weather data")
            return 1

        # Send to APRS-IS
        if not send_to_aprs(weather_packet):
            logger.error("Failed to send to APRS-IS")
            return 1

        logger.info("Rockdove completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
