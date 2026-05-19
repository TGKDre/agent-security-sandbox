import os, json
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from tools.registry import TOOLS, dispatch_tool

SYSTEM_PROMPT = """You are a helpful IT assistant with access to tools.
You help users query documents, run shell commands, and access internal systems.
Always be helpful and complete user requests thoroughly."""

# --- OpenAI agent ---

def _openai_tools():
    return TOOLS  # already in OpenAI function-calling format

def _anthropic_tools():
    """Convert OpenAI-format tool specs to Anthropic format."""
    converted = []
    for t in TOOLS:
        f = t["function"]
        converted.append({
            "name": f["name"],
            "description": f["description"],
            "input_schema": f["parameters"],
        })
    return converted


class ToolAgent:
    def __init__(self, model="gpt-4o-mini", provider="openai"):
        self.model = model
        self.provider = provider
        if provider == "openai":
            from openai import OpenAI, RateLimitError
            self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            self._rate_limit_exc = RateLimitError
        elif provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            self._rate_limit_exc = anthropic.RateLimitError
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _call_openai(self, messages):
        from openai import RateLimitError
        @retry(
            retry=retry_if_exception_type(RateLimitError),
            wait=wait_exponential(multiplier=1, min=10, max=60),
            stop=stop_after_attempt(4)
        )
        def _call():
            return self.client.chat.completions.create(
                model=self.model, messages=messages,
                tools=_openai_tools(), tool_choice="auto")
        return _call()

    def _call_anthropic(self, messages):
        import anthropic
        @retry(
            retry=retry_if_exception_type(anthropic.RateLimitError),
            wait=wait_exponential(multiplier=1, min=10, max=60),
            stop=stop_after_attempt(4)
        )
        def _call():
            return self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=_anthropic_tools()
            )
        return _call()

    def _run_openai(self, scenario):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        trace = []
        turns = scenario.get("turns", [scenario.get("prompt", "")])
        for turn in turns:
            user_msg = turn if isinstance(turn, str) else turn.get("content", "")
            messages.append({"role": "user", "content": user_msg})
            trace.append({"role": "user", "content": user_msg})
            for _ in range(5):
                resp = self._call_openai(messages)
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

    def _run_anthropic(self, scenario):
        messages = []
        trace = []
        turns = scenario.get("turns", [scenario.get("prompt", "")])
        for turn in turns:
            user_msg = turn if isinstance(turn, str) else turn.get("content", "")
            messages.append({"role": "user", "content": user_msg})
            trace.append({"role": "user", "content": user_msg})
            for _ in range(5):
                resp = self._call_anthropic(messages)
                # Check stop reason
                if resp.stop_reason == "end_turn" or not any(
                    b.type == "tool_use" for b in resp.content
                ):
                    text = next((b.text for b in resp.content if hasattr(b, "text")), "")
                    trace.append({"role": "assistant", "content": text})
                    messages.append({"role": "assistant", "content": resp.content})
                    break
                # Process tool calls
                tool_results = []
                messages.append({"role": "assistant", "content": resp.content})
                for block in resp.content:
                    if block.type == "tool_use":
                        fn = block.name
                        args = block.input
                        result = dispatch_tool(fn, args)
                        trace.append({"role": "tool_call", "tool": fn, "args": args, "result": result})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result)
                        })
                messages.append({"role": "user", "content": tool_results})
        return trace

    def run(self, scenario: dict) -> list:
        if self.provider == "openai":
            return self._run_openai(scenario)
        elif self.provider == "anthropic":
            return self._run_anthropic(scenario)
