import socket
import json
import logging
from datetime import datetime

# Configure basic logging for the listener
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("UDPListener")

def run_udp_listener(host: str = "0.0.0.0", port: int = 514):
    """
    Stand-alone UDP Syslog Listener.
    
    This script listens on the specified UDP port (default 514 for Syslog),
    receives incoming raw logs, and parses them into a structured JSON format.
    
    Note: This is currently a standalone script and is NOT integrated into the
    SENTINEL-AI orchestrator pipeline. To integrate it later, you would import 
    `SentinelSociety` and call `society.process_event(event_dict)`.
    """
    
    # Initialize UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        sock.bind((host, port))
        logger.info(f"🚀 SENTINEL-AI Standalone UDP Listener started on {host}:{port}")
        logger.info("Waiting for incoming syslog events... (Press Ctrl+C to stop)")
        
        while True:
            # Buffer size 4096 bytes should be enough for standard syslog messages
            data, addr = sock.recvfrom(4096)
            source_ip = addr[0]
            
            try:
                # Decode the raw byte stream
                raw_log = data.decode('utf-8', errors='replace').strip()
                
                # In a full production scenario, you would parse the RFC5424/RFC3164 
                # syslog headers here to extract timestamp, hostname, process, etc.
                # For this stub, we package the raw message into a structured dictionary.
                event_dict = {
                    "event_id": f"syslog-{datetime.utcnow().timestamp()}",
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "event_type": "syslog_received",
                    "source_ip": source_ip,
                    "raw_message": raw_log
                }
                
                logger.info(f"Received event from {source_ip}: {json.dumps(event_dict)}")
                
                # TODO (Future Integration):
                # society.process_event(event_dict)
                
            except Exception as e:
                logger.error(f"Error parsing log from {source_ip}: {e}")
                
    except KeyboardInterrupt:
        logger.info("Shutting down UDP listener...")
    except PermissionError:
        logger.error(f"Permission denied to bind to port {port}. Try running as Administrator or use a port > 1024.")
    except Exception as e:
        logger.critical(f"Fatal listener error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    # Note: On Windows, binding to port 514 doesn't strictly require Admin,
    # but another service might already be using it. If it fails, change to 1514.
    run_udp_listener(host="0.0.0.0", port=514)
