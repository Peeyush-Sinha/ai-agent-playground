"""
main.py
-------
Command-line interface for RescueCoordinator.

Usage:
    export API_KEY=sk-ant-...
    python main.py

Example prompts to try:
    "There's been a reported earthquake near lat 34.05, lon -118.25
     (downtown LA). Pull in all available reports, cluster them, score
     the incidents, log the top ones, and give me a ranked briefing."

    "Flooding reported near lat 29.76, lon -95.37 (Houston). Check
     sensor and social feeds only, and tell me the two highest
     priority spots."

    "Show me all currently logged incidents, most urgent first."
"""

import os
import sys
from agent import Agent


def main():
    if not os.environ.get("API_KEY"):
        print("Warning: API_KEY is not set. Set it before running, e.g.:")
        print("  export API_KEY=sk-ant-...\n")

    print("=" * 70)
    print("RescueCoordinator — disaster response decision-support agent")
    print("Data sources are SIMULATED for this demo")
    print("=" * 70)
    print("\nExample: 'Earthquake reported near lat 34.05, lon -118.25. Pull all")
    print("feeds, cluster, score, log the top incidents, and brief me.'\n")
    print("Type 'quit' to exit.\n")

    agent = Agent(verbose=True)

    while True:
        try:
            user_input = input("Coordinator request: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            sys.exit(0)

        if user_input.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break
        if not user_input:
            continue

        answer = agent.run(user_input)
        print(f"\n--- Agent briefing ---\n{answer}\n")


if __name__ == "__main__":
    main()
