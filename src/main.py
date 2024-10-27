from config import *
from metar import Metar
from typing import Optional, NamedTuple
import logging
import requests
import socket
from math import exp
from datetime import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - Rockdove - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Rockdove")


class WeatherData(NamedTuple):
    metar: str
    visibility: str
    sky: str
    conditions: str


def calculate_humidity(temp_c: float, dewpoint_c: float) -> int:
    b, c = 17.625, 243.04
    gamma_t = (b * temp_c) / (c + temp_c)
    gamma_d = (b * dewpoint_c) / (c + dewpoint_c)
    return int(round(100 * exp(gamma_d - gamma_t)))


def parse_metar(metar_string: str) -> Optional[Metar.Metar]:
    if not metar_string:
        return None

    metar_string = metar_string.removeprefix("METAR ").removesuffix("=")
    try:
        return Metar.Metar(metar_string)
    except Exception as e:
        logger.error(f"Error parsing METAR: {e}")
        return None


def decimal_to_ddmmss(decimal_degrees: float, is_latitude: bool = True) -> str:
    absolute = abs(decimal_degrees)
    degrees = int(absolute)
    minutes = (absolute - degrees) * 60

    if is_latitude:
        return f"{degrees:02d}{minutes:05.2f}{'S' if decimal_degrees < 0 else 'N'}"
    return f"{degrees:03d}{minutes:05.2f}{'W' if decimal_degrees < 0 else 'E'}"


def fetch_weather_data() -> Optional[WeatherData]:
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()

        if not data.get("status"):
            return None

        api_data = data["data"]
        return WeatherData(
            metar=api_data.get("metar", ""),
            visibility=api_data.get("visibilidade", "NA"),
            sky=api_data.get("ceu", "NA"),
            conditions=api_data.get("condicoes_tempo", "NA"),
        )
    except Exception as e:
        logger.error(f"Error fetching API data: {e}")
        return None


def format_aprs_weather(obs: Metar.Metar) -> str:
    lat, lon = float(OBJECT_LAT), float(OBJECT_LON)
    position = f"{decimal_to_ddmmss(lat)}/{decimal_to_ddmmss(lon, False)}"

    wind_speed_mph = int(obs.wind_speed.value() * 1.15078) if obs.wind_speed else 0
    temp_f = int(obs.temp.value() * 1.8 + 32) if obs.temp else 0
    pressure = int(obs.press.value() * 10) if obs.press else 0
    wind_dir = int(obs.wind_dir.value()) if obs.wind_dir else 0

    humidity = (
        calculate_humidity(obs.temp.value(), obs.dewpt.value())
        if obs.temp and obs.dewpt
        else 0
    )

    return (
        f"@{obs.time.strftime('%d%H%M')}z"
        f"{position}"
        f"_{wind_dir:03d}/{wind_speed_mph:03d}"
        f"g...t{temp_f:03d}r...p...h{humidity:02d}b{pressure:05d}"
    )


def send_to_aprs(
    weather_packet: str, weather_data: WeatherData, obs: Metar.Metar
) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)

    try:
        sock.connect((SERVER, PORT))
        sock.recv(1024)

        login = f"user {CALLSIGN} pass {PASSWORD} vers Rockdove 0.1\n"
        sock.send(login.encode())

        if "unverified" in sock.recv(1024).decode().lower():
            logger.error("APRS-IS login failed")
            return False

        object_name = f"{OBJECT_ID:<9}"
        lat, lon = float(OBJECT_LAT), float(OBJECT_LON)
        position = f"{decimal_to_ddmmss(lat)}/{decimal_to_ddmmss(lon, False)}"
        timestamp = obs.time.strftime("%H%M%S")
        readable_timestamp = obs.time.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Send weather object
        weather_object = (
            f"{CALLSIGN}>APRKDV,TCPIP*:"
            f";{object_name}*{timestamp}h"
            f"{position}_{weather_packet[weather_packet.find('_')+1:]}\n"
        )
        sock.send(weather_object.encode())
        logger.info(f"Sent weather object: {weather_object.strip()}")

        # Send position object
        comment = (
            f"Obs {readable_timestamp} - "
            f"Vis {weather_data.visibility} Ceu {weather_data.sky} "
            f"- {weather_data.conditions}"
        )

        if len(DATA_COMMENT) > 0:
            comment = f"{comment} - {DATA_COMMENT}"

        position_object = (
            f"{CALLSIGN}>APRKDV,TCPIP*:"
            f";{object_name}*{timestamp}h"
            f"{position}^{comment}\n"
        )
        sock.send(position_object.encode())
        logger.info(f"Sent position object: {position_object.strip()}")

        return True

    except Exception as e:
        logger.error(f"Error sending to APRS-IS: {e}")
        return False
    finally:
        sock.close()


def main() -> int:
    logger.info("Rockdove starting")

    try:
        weather_data = fetch_weather_data()
        if not weather_data:
            logger.error("Failed to fetch weather data")
            return 1

        obs = parse_metar(weather_data.metar)
        if not obs:
            logger.error("Failed to parse METAR data")
            return 1

        weather_packet = format_aprs_weather(obs)
        if not send_to_aprs(weather_packet, weather_data, obs):
            logger.error("Failed to send to APRS-IS")
            return 1

        logger.info("Rockdove completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
