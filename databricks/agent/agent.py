import mlflow
from typing import Any, Optional
from databricks_langchain import ChatDatabricks, UCFunctionToolkit
from langgraph.prebuilt import create_react_agent
from mlflow.pyfunc import ChatAgent
from mlflow.types.agent import ChatAgentMessage, ChatAgentResponse, ChatAgentChunk

mlflow.langchain.autolog()

llm = ChatDatabricks(endpoint="databricks-meta-llama-3-3-70b-instruct")
tools = UCFunctionToolkit(
    function_names=["suppliers_catalog.gold.get_supplier_index"]
).tools

SYSTEM = (
    "You answer questions about supplier performance. ALWAYS call get_supplier_index. "
    "The index is 0-100. Classify it: 75+ = Strong, 40-74 = Moderate, below 40 = Needs attention. "
    "Reply in at most 2 short sentences. Format: "
    "'<Supplier>: <index>/100 (<rating>). Strongest: <best factor>; weakest: <worst factor>.' "
    "Use friendly factor names (on-time delivery, lead-time reliability, delivery consistency, "
    "order fill rate, order cancellations). No raw column names, no factor list, no 'pts', no extra commentary. "
    "If no supplier matches, say so in one sentence."
)

graph = create_react_agent(llm, tools, prompt=SYSTEM)


class SupplierAgent(ChatAgent):
    def predict(self, messages, context=None, custom_inputs=None) -> ChatAgentResponse:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        result = graph.invoke({"messages": msgs})
        last = result["messages"][-1]
        return ChatAgentResponse(
            messages=[ChatAgentMessage(role="assistant", content=last.content, id="1")]
        )


AGENT = SupplierAgent()
mlflow.models.set_model(AGENT)