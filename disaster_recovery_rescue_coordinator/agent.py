"""
agent.py
--------
The RescueCoordinator agent loop: same Reason -> Act -> Observe pattern
as a standard tool-using AI agent, with a system prompt and toolset
specialized for triaging disaster reports.

This is a decision-support demo, not a dispatch system. In a real
deployment, this agent's output should always be reviewed by a trained
human coordinator before any resources are actually dispatched. The
"data sources" here are synthetic — a real system would need verified,
low-latency integrations and careful handling of false positives
(sending rescuers to the wrong place has a real cost).
"""

import os
from anthropic import Anthropic
from tools import TOOL_SCHEMAS, TOOL_REGISTRY

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
MAX_STEPS = 12  # generously higher than a simple agent, since this task chains many tool calls

SYSTEM_PROMPT = """You are RescueCoordinator, a decision-support agent that helps
human disaster-response coordinators triage where to send help first after an
earthquake or flood.

You have tools to:
  - pull reports from satellite imagery, social media, and sensor feeds
  - cluster nearby reports into single incidents (multiple reports about the
    same collapsed building should become one incident, not several)
  - score each incident's priority (0-100) based on report volume, source
    diversity, confidence, and recency
  - log the highest-priority incidents with a short plain-language summary

Your typical workflow for a request:
  1. Fetch reports from all three feeds for the area in question.
  2. Combine them into one JSON array and pass that array to cluster_reports.
  3. Call score_incident on each resulting cluster.
  4. Save the incidents that clear a reasonable priority bar (use judgment;
     don't save every low-signal cluster) via save_incident, writing a
     clear, calm, factual summary a responder could act on.
  5. Finish with a short plain-text ranked list of the top incidents and
     why each is prioritized where it is.

Always caveat that this is decision support based on automated/simulated
signals, not a verified ground-truth report, and that a human should
confirm before dispatching resources. Be concise and factual — responders
are reading this under time pressure."""


class Agent:
    def __init__(self, api_key: str | None = None, verbose: bool = True):
        self.client = Anthropic(api_key=api_key)
        self.verbose = verbose
        self.messages = []

    def _log(self, *args):
        if self.verbose:
            print(*args)

    def run(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})

        for step in range(MAX_STEPS):
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=self.messages,
            )

            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return "".join(
                    block.text for block in response.content if block.type == "text"
                )

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                self._log(f"[step {step + 1}] calling tool: {block.name}({_short(block.input)})")
                result = self._execute_tool(block.name, block.input)
                self._log(f"[step {step + 1}] result: {_short(result)}")
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )

            self.messages.append({"role": "user", "content": tool_results})

        return "Reached the maximum number of reasoning steps without a final answer."

    @staticmethod
    def _execute_tool(name: str, tool_input: dict) -> str:
        fn = TOOL_REGISTRY.get(name)
        if fn is None:
            return f"Error: unknown tool '{name}'"
        try:
            return fn(**tool_input)
        except Exception as e:
            return f"Error running tool '{name}': {e}"


def _short(x, limit=200) -> str:
    s = str(x)
    return s if len(s) <= limit else s[:limit] + "...(truncated)"
