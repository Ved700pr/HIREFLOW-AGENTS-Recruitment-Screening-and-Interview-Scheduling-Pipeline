"""Base class for every agent.

Each agent owns a Microsoft Semantic Kernel `Kernel` with ONE plugin holding that
agent's tools. The tools stay plain Python functions; the kernel just registers
and invokes them, and every call is written to the run log.
"""
from semantic_kernel import Kernel
from semantic_kernel.functions import KernelArguments, kernel_function

from hireflow.runtime import run_sync


class BaseAgent:
    name = "agent"        # also the Semantic Kernel plugin name (letters, digits, underscore)
    role = ""             # one-line job description of the agent
    tools: list = []      # plain Python functions

    def __init__(self):
        self.kernel = Kernel()
        functions = {
            fn.__name__: kernel_function(fn, name=fn.__name__, description=(fn.__doc__ or "").strip().split("\n")[0])
            for fn in self.tools
        }
        self.kernel.add_plugin(functions, plugin_name=self.name)
        self.log = None

    def call(self, function_name: str, ctx: str = "", **kwargs):
        """Invoke one of this agent's tools through the Semantic Kernel and log it."""
        result = run_sync(
            self.kernel.invoke(
                plugin_name=self.name,
                function_name=function_name,
                arguments=KernelArguments(**kwargs),
            )
        )
        if self.log:
            self.log.write(self.name, "tool_call", f"{function_name}({ctx})")
        return result.value

    def say(self, event: str, detail: str = "") -> None:
        if self.log:
            self.log.write(self.name, event, detail)

    def run(self, pool) -> None:  # pragma: no cover - implemented by each agent
        raise NotImplementedError
