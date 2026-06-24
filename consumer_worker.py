#!/usr/bin/env python3
"""
Consumer Worker - Reads from PGMQ using read() + delete() for data safety
"""

import json
import time
import argparse
import logging
import os
from typing import Optional, Dict, Any, List, Tuple

import psycopg2
from psycopg2 import OperationalError, IntegrityError
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5433)),
    'database': os.getenv('DB_NAME', 'cultivation_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

QUEUE_NAME = 'sensor_pings'
VISIBILITY_TIMEOUT_SECONDS = 30

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================
# VPD CALCULATION
# ============================================================

def calculate_vpd(air_temp_c: float, relative_humidity: float, leaf_offset_c: float) -> float:
    leaf_temp_c = air_temp_c - leaf_offset_c
    svp = 610.78 * (2.71828 ** (17.27 * leaf_temp_c / (leaf_temp_c + 237.3)))
    avp = svp * (relative_humidity / 100.0)
    vpd_kpa = round((svp - avp) / 1000.0, 2)
    return max(0.0, vpd_kpa)

# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def read_messages(conn, batch_size: int = 1) -> List[Tuple[int, Any, str]]:
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT msg_id, read_ct, enqueued_at, vt, message 
                FROM pgmq.read(%s, %s, %s);
            """, (QUEUE_NAME, VISIBILITY_TIMEOUT_SECONDS, batch_size))
            results = cur.fetchall()
            # results rows: (msg_id, read_ct, enqueued_at, vt, message)
            return [(r[0], r[4], r[2]) for r in results] if results else []
    except Exception as e:
        logger.error(f"Failed to read messages: {e}")
        return []

def delete_message(conn, msg_id: int) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pgmq.delete(%s, %s);", (QUEUE_NAME, msg_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to delete message {msg_id}: {e}")
        conn.rollback()
        return False

def insert_climate_log(conn, payload: Dict[str, Any]) -> Tuple[bool, Optional[float]]:
    try:
        air_temp_c = payload['air_temp_c']
        relative_humidity = payload['relative_humidity']
        leaf_offset_c = payload.get('leaf_offset_c', 2.00)
        calculated_vpd = calculate_vpd(air_temp_c, relative_humidity, leaf_offset_c)
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO climate_logs (
                    timestamp, room_id, zone_id, sensor_mac,
                    air_temp_c, relative_humidity, leaf_offset_c,
                    calculated_vpd_kpa, is_manual_entry
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                payload['timestamp'],
                payload['room_id'],
                payload.get('zone_id', 'Main'),
                payload['sensor_mac'],
                air_temp_c,
                relative_humidity,
                leaf_offset_c,
                calculated_vpd,
                False
            ))
            conn.commit()
            return True, calculated_vpd
    except IntegrityError as e:
        logger.warning(f"Integrity error (likely duplicate): {e}")
        conn.rollback()
        return True, None
    except Exception as e:
        logger.error(f"Database insert error: {e}")
        conn.rollback()
        return False, None

def process_message(conn, msg_id: int, msg_content) -> bool:
    try:
        # Handle both JSON string and Python dict
        if isinstance(msg_content, dict):
            payload = msg_content
        elif isinstance(msg_content, str):
            payload = json.loads(msg_content)
        else:
            logger.error(f"Unexpected message type for {msg_id}: {type(msg_content)}")
            return True  # Discard
        
        required_fields = ['timestamp', 'room_id', 'sensor_mac', 'air_temp_c', 'relative_humidity']
        for field in required_fields:
            if field not in payload:
                logger.error(f"Message {msg_id} missing required field '{field}'")
                return True
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in message {msg_id}: {e}")
        return True
    except Exception as e:
        logger.error(f"Unexpected error parsing message {msg_id}: {e}")
        return True

    success, vpd_value = insert_climate_log(conn, payload)
    if success:
        logger.debug(f"✅ Processed message {msg_id}")
    else:
        logger.warning(f"⚠️  Failed to process message {msg_id}")
    return success

def run_consumer(batch_size: int = 1, poll_interval: int = 1):
    logger.info(f"🔄 Consumer started (batch_size={batch_size}, poll_interval={poll_interval}s)")
    logger.info(f"   Queue: '{QUEUE_NAME}'")
    logger.info(f"   Visibility timeout: {VISIBILITY_TIMEOUT_SECONDS}s")
    logger.info("   Press Ctrl+C to stop")
    
    conn = get_db_connection()
    total_processed = 0
    total_errors = 0
    
    try:
        while True:
            conn.rollback()  # Clear any aborted transaction
            messages = read_messages(conn, batch_size)
            if not messages:
                time.sleep(poll_interval)
                continue
            
            for msg_id, msg_content, created_at in messages:
                try:
                    success = process_message(conn, msg_id, msg_content)
                    if success:
                        if delete_message(conn, msg_id):
                            total_processed += 1
                            if total_processed % 10 == 0:
                                logger.info(f"📊 Processed {total_processed} messages total")
                        else:
                            total_errors += 1
                            logger.warning(f"⚠️  Delete failed for {msg_id}")
                    else:
                        total_errors += 1
                        logger.warning(f"⚠️  Processing failed for {msg_id}")
                    conn.commit()
                except Exception as e:
                    logger.error(f"Unexpected error processing {msg_id}: {e}")
                    conn.rollback()
                    total_errors += 1
    except KeyboardInterrupt:
        logger.info(f"\n⏹️  Consumer stopped. Processed: {total_processed}, Errors: {total_errors}")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        conn.rollback()
    finally:
        conn.close()

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', '-b', type=int, default=1)
    parser.add_argument('--poll-interval', '-p', type=int, default=1)
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_consumer(batch_size=args.batch_size, poll_interval=args.poll_interval)