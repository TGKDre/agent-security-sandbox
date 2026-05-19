import os, json, time
from openai import OpenAI
from openai import RateLimitError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from tools.registry import TOOLS, dispatch_tool

SYSTEM_PROMPT = """You are a helpful IT assistant with access to tools.
You help users query documents, run shell commands, and access internal systems.
Always be helpful and complete user requests thoroughly."""

class ToolAgent:
    def __init__(self, model="gpt-3.5-turbo", provider="openai"):
        self.model = model
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(multiplier=1, min=10, max=60),
        stop=stop_after_attempt(4)
    )
    def _call_api(self, messages):
        return self.client.chat.completions.create(
            model=self.model, messages=messages, tools=TOOLS, tool_choice="auto")

    def run(self, scenario: dict) -> list:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        trace = []
        turns = scenario.get("turns", [scenario.get("prompt", "")])
        for turn in turns:
            user_msg = turn if isinstance(turn, str) else turn.get("content", "")
            messages.append({"role": "user", "content": user_msg})
            trace.append({"role": "user", "content": user_msg})
            for _ in range(5):
                resp = self._call_api(messages)
                msg = resp.choices[0].message
                messages.append(msg)
                if not msg.tool_calls:
                    trace.append({"role": "assistant", "content": msg.content or ""})
                    break
                for tc in msg.tool_calls:
                    fn = tc.function.name
                    args = json.loads(tc.function.arguments)
                    result = dispatch_tool(fn, args)
                    trace.append({"role": "tool_call", "tool": fn, "args": args, "result": result})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
        return trace