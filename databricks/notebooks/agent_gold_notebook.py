# Databricks notebook source
# MAGIC %sql
# MAGIC create or replace function suppliers_catalog.gold.get_supplier_index(
# MAGIC     supplier_query string comment 'supplier id or name to look up'
# MAGIC )
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
# MAGIC comment 'Supplier performance index (0-100) and per-factor point contributions.'
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
# MAGIC     "You answer supplier performance questions. ALWAYS call get_supplier_index. "
# MAGIC     "The index is 0-100. The factor point columns and their MAX possible points are: "
# MAGIC     "on_time_rate_pts (max 35) = on-time delivery; "
# MAGIC     "avg_lead_variance_pts (max 25) = lead-time accuracy; "
# MAGIC     "lead_variance_std_pts (max 15) = delivery consistency; "
# MAGIC     "fill_rate_pts (max 15) = order fill rate; "
# MAGIC     "cancel_rate_pts (max 10) = order reliability (avoiding cancellations). "
# MAGIC     "A factor needs improvement when its points are low relative to its max (below ~half). "
# MAGIC     "Rules: "
# MAGIC     "If the index is 60 or below, reply with the index and rating, then list ONLY the areas that need improvement, in plain language. "
# MAGIC     "If the index is above 60, reply with the index and rating, briefly note what the supplier does well (factors near their max), AND list any remaining areas to improve. "
# MAGIC     "Keep it to 2-3 short sentences, plain business language, no column names, no raw point numbers. "
# MAGIC     "If no supplier matches, say so in one sentence."
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

#from agent import AGENT
#from mlflow.types.agent import ChatAgentMessage

# testing the agent before deploying
#r = AGENT.predict([ChatAgentMessage(role="user", content="How is Vertex Adhesives performing?", id="1")])
#print(r.messages[-1].content)

# COMMAND ----------

# MAGIC %pip install -U -qqqq databricks-langchain "langgraph==0.6.7" "langgraph-prebuilt==0.6.4" databricks-agents mlflow
# MAGIC dbutils.library.restartPython()

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

# deploying
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

