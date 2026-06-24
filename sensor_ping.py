#!/usr/bin/env python3
"""
Sensor Ping Script - Publishes mock sensor data to PGMQ

Usage:
    python3 sensor_ping.py [--interval SECONDS] [--room ROOM_ID] [--zone ZONE_ID]
"""

import json
import random
import time
import argparse
import logging
import os
from datetime import datetime
from typing import Dict, Tuple, Optional

import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================
# CONFIGURATION FROM ENVIRONMENT
# ============================================================

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5433)),
    'database': os.getenv('DB_NAME', 'cultivation_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

QUEUE_NAME = 'sensor_pings'

# Default sensor identity
DEFAULT_SENSOR_MAC = 'AA:BB:CC:DD:EE:FF'
DEFAULT_ROOM_ID = 'tent_1'
DEFAULT_ZONE_ID = 'Main'

# Realistic sensor reading ranges
TEMP_MIN = 22.0
TEMP_MAX = 26.0
HUMIDITY_MIN = 55.0
HUMIDITY_MAX = 75.0
OFFSET_MIN = 1.5
OFFSET_MAX = 3.0

# ============================================================
# LOGGING SETUP
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================
# CORE FUNCTIONS
# ============================================================

def get_db_connection() -> psycopg2.extensions.connection:
    """Establish a database connection with retries."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except OperationalError as e:
            logger.warning(f"Connection attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)
    raise RuntimeError("Failed to connect to database after 3 attempts")


def generate_sensor_reading() -> Tuple[float, float, float]:
    """Generate realistic sensor data."""
    return (
        round(random.uniform(TEMP_MIN, TEMP_MAX), 2),
        round(random.uniform(HUMIDITY_MIN, HUMIDITY_MAX), 2),
        round(random.uniform(OFFSET_MIN, OFFSET_MAX), 2)
    )


def create_sensor_payload(
    sensor_mac: str,
    room_id: str,
    zone_id: str,
    air_temp_c: float,
    relative_humidity: float,
    leaf_offset_c: float
) -> Dict:
    """Create a JSON payload for the sensor ping."""
    return {
        'sensor_mac': sensor_mac,
        'room_id': room_id,
        'zone_id': zone_id,
        'air_temp_c': air_temp_c,
        'relative_humidity': relative_humidity,
        'leaf_offset_c': leaf_offset_c,
        'timestamp': datetime.now().isoformat()
    }


def publish_sensor_ping(conn, payload: Dict) -> Optional[int]:
    """Publish a sensor reading to the PGMQ queue."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT pgmq.send('{QUEUE_NAME}', %s);",
                (json.dumps(payload),)
            )
            msg_id = cur.fetchone()[0]
            conn.commit()
            return msg_id
    except Exception as e:
        logger.error(f"Failed to publish message: {e}")
        conn.rollback()
        return None


def run_ping_loop(interval_seconds: int, sensor_mac: str, room_id: str, zone_id: str):
    """Main loop - generates and publishes sensor pings."""
    logger.info(f"🔄 Starting sensor ping loop (interval={interval_seconds}s)")
    logger.info(f"   Sensor: {sensor_mac} | Room: {room_id} | Zone: {zone_id}")
    logger.info("   Press Ctrl+C to stop")
    
    conn = get_db_connection()
    count = 0
    success_count = 0
    
    try:
        while True:
            air_temp_c, relative_humidity, leaf_offset_c = generate_sensor_reading()
            payload = create_sensor_payload(
                sensor_mac, room_id, zone_id,
                air_temp_c, relative_humidity, leaf_offset_c
            )
            
            msg_id = publish_sensor_ping(conn, payload)
            count += 1
            
            if msg_id is not None:
                success_count += 1
                logger.info(
                    f"📤 [{count:03d}] {air_temp_c}°C | {relative_humidity}% RH "
                    f"| Offset: {leaf_offset_c}°C → Msg ID: {msg_id}"
                )
            else:
                logger.warning(f"⚠️  [{count:03d}] Publish failed")
            
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        logger.info(f"\n⏹️  Ping loop stopped. Sent: {count}, Success: {success_count}")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        conn.close()


# ============================================================
# COMMAND LINE INTERFACE
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Sensor Ping Script")
    parser.add_argument('--interval', '-i', type=int, default=5, help="Interval between pings (default: 5)")
    parser.add_argument('--room', '-r', type=str, default=DEFAULT_ROOM_ID, help=f"Room ID (default: {DEFAULT_ROOM_ID})")
    parser.add_argument('--zone', '-z', type=str, default=DEFAULT_ZONE_ID, help=f"Zone ID (default: {DEFAULT_ZONE_ID})")
    parser.add_argument('--sensor', '-s', type=str, default=DEFAULT_SENSOR_MAC, help=f"Sensor MAC (default: {DEFAULT_SENSOR_MAC})")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_ping_loop(
        interval_seconds=args.interval,
        sensor_mac=args.sensor,
        room_id=args.room,
        zone_id=args.zone
    )