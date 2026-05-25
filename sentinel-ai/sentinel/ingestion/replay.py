import time
import json
import argparse
import sys
from pathlib import Path
from rich.console import Console

from sentinel.orchestration.society import SentinelSociety
from sentinel.orchestration.message_bus import bus, AgentMessage
from sentinel.config import SENTINEL_REPLAY_RATE

console = Console()

def replay_scenario(scenario_path: str, rate: float):
    path = Path(scenario_path)
    if not path.exists():
        console.print(f"[bold red]Error: Scenario file {scenario_path} not found.[/bold red]")
        sys.exit(1)
        
    society = SentinelSociety()
    
    console.print(f"[bold green]Starting replay of {path.name} at {rate} events/sec...[/bold green]")
    bus.publish(AgentMessage(from_agent="System", kind="info", content=f"Starting replay of {path.name}"))
    
    delay = 1.0 / rate if rate > 0 else 0
    
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                event = json.loads(line)
                
                # Publish the raw event to the bus so UI can show it
                bus.publish(AgentMessage(
                    from_agent="System", 
                    kind="info", 
                    content=f"Ingested event: {event.get('event_type')} from {event.get('src_ip')}"
                ))
                
                # Process the event
                result = society.process_event(event)
                
                if result.get("status") == "investigated":
                     console.print(f"[yellow]Incident created: {result.get('incident_id')}[/yellow]")
                     
                if delay > 0:
                    time.sleep(delay)
                    
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Replay stopped by user.[/bold yellow]")
        bus.publish(AgentMessage(from_agent="System", kind="info", content="Replay stopped by user."))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay a JSONL scenario file.")
    parser.add_argument("--scenario", required=True, help="Path to the JSONL scenario file.")
    parser.add_argument("--rate", type=float, default=SENTINEL_REPLAY_RATE, help="Events per second.")
    args = parser.parse_args()
    
    replay_scenario(args.scenario, args.rate)
