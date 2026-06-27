# Databricks notebook source
# MAGIC %sql
# MAGIC create or replace function suppliers_catalog.gold.get_supplier_index(supplier_query string)
# MAGIC returns table (
# MAGIC     supplier_id string,
# MAGIC     supplier_name string,
# MAGIC     supplier_index double,
# MAGIC     on_time_rate_pts double,
# MAGIC     avg_lead_variance_pts double,
# MAGIC     lead_variance_std_pts double,
# MAGIC     fill_rate_pts double,
# MAGIC     cancel_rate_pts double
# MAGIC )
# MAGIC comment 'Returns the supplier performance index and contributing factor points, matched by supplier id or name.'
# MAGIC return 
# MAGIC     select
# MAGIC         supplier_id,
# MAGIC         supplier_name,
# MAGIC         supplier_index,
# MAGIC         on_time_rate_pts,
# MAGIC         avg_lead_variance_pts,
# MAGIC         lead_variance_std_pts,
# MAGIC         fill_rate_pts,
# MAGIC         cancel_rate_pts
# MAGIC     from
# MAGIC         suppliers_catalog.gold.supplier_index
# MAGIC     where
# MAGIC         supplier_id = supplier_query 
# MAGIC         or
# MAGIC         lower(supplier_name) like lower(concat('%', supplier_query, '%'));

# COMMAND ----------

# MAGIC %sql
# MAGIC -- testing
# MAGIC select * from suppliers_catalog.gold.get_supplier_index('Vertex')

# COMMAND ----------

# Building the Agent

# COMMAND ----------

import importlib.metadata as m
print("langgraph", m.version("langgraph"))
print("langgraph-prebuilt", m.version("langgraph-prebuilt"))
print("langchain-core", m.version("langchain-core"))

# COMMAND ----------

# MAGIC %%writefile agent.py
# MAGIC import mlflow
# MAGIC from typing import Any, Optional
# MAGIC from databricks_langchain import ChatDatabricks, UCFunctionToolkit
# MAGIC from langgraph.prebuilt import create_react_agent
# MAGIC from mlflow.pyfunc import ChatAgent
# MAGIC from mlflow.types.agent import ChatAgentMessage, ChatAgentResponse, ChatAgentChunk
# MAGIC
# MAGIC mlflow.langchain.autolog()
# MAGIC
# MAGIC llm = ChatDatabricks(endpoint="databricks-meta-llama-3-3-70b-instruct")
# MAGIC tools = UCFunctionToolkit(
# MAGIC     function_names=["suppliers_catalog.gold.get_supplier_index"]
# MAGIC ).tools
# MAGIC
# MAGIC SYSTEM = (
# MAGIC     "You answer questions about supplier performance. "
# MAGIC     "ALWAYS call get_supplier_index. Report the index (0-100) and explain it using the factor points. "
# MAGIC     "Translate the raw factor names into plain business language: "
# MAGIC     "on_time_rate_pts = 'on-time delivery', "
# MAGIC     "avg_lead_variance_pts = 'lead-time reliability', "
# MAGIC     "lead_variance_std_pts = 'delivery consistency', "
# MAGIC     "fill_rate_pts = 'order fill rate', "
# MAGIC     "cancel_rate_pts = 'order cancellations'. "
# MAGIC     "Name the strongest and weakest factor using these friendly names, and don't show the raw column names or the word 'pts'. "
# MAGIC     "Never invent numbers. If no supplier matches, say so."
# MAGIC )
# MAGIC
# MAGIC graph = create_react_agent(llm, tools, prompt=SYSTEM)
# MAGIC
# MAGIC
# MAGIC class SupplierAgent(ChatAgent):
# MAGIC     def predict(self, messages, context=None, custom_inputs=None) -> ChatAgentResponse:
# MAGIC         msgs = [{"role": m.role, "content": m.content} for m in messages]
# MAGIC         result = graph.invoke({"messages": msgs})
# MAGIC         last = result["messages"][-1]
# MAGIC         return ChatAgentResponse(
# MAGIC             messages=[ChatAgentMessage(role="assistant", content=last.content, id="1")]
# MAGIC         )
# MAGIC
# MAGIC
# MAGIC AGENT = SupplierAgent()
# MAGIC mlflow.models.set_model(AGENT)

# COMMAND ----------

from agent import AGENT
from mlflow.types.agent import ChatAgentMessage

# testing the agent before deploying
r = AGENT.predict([ChatAgentMessage(role="user", content="How is Vertex Adhesives performing?", id="1")])
print(r.messages[-1].content)

# COMMAND ----------

# logging to unity catalog with mlflow
import mlflow
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksFunction

UC_MODEL = "suppliers_catalog.gold.supplier_agent"
mlflow.set_registry_uri("databricks-uc")

with mlflow.start_run():
    info = mlflow.pyfunc.log_model(
        python_model="agent.py",
        artifact_path="agent",
        registered_model_name=UC_MODEL,
        input_example={"messages": [{"role": "user", "content": "How is Vertex Adhesives performing?"}]},
        resources=[
            DatabricksServingEndpoint(endpoint_name="databricks-meta-llama-3-3-70b-instruct"),
            DatabricksFunction(function_name="suppliers_catalog.gold.get_supplier_index"),
        ],
        pip_requirements=["databricks-langchain", "langgraph==0.6.7",
                          "langgraph-prebuilt==0.6.4", "databricks-agents", "mlflow"],
    )

# COMMAND ----------

from databricks import agents
agents.deploy(UC_MODEL, info.registered_model_version)

# COMMAND ----------

# testing the deployed version
from mlflow.deployments import get_deploy_client
client = get_deploy_client("databricks")
r = client.predict(
    endpoint="agents_suppliers_catalog-gold-supplier_agent",
    inputs={"messages": [{"role": "user", "content": "How is Vertex Adhesives performing?"}]},
)
print(r)

# COMMAND ----------

