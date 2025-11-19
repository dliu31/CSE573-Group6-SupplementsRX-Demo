# SupplementsRX AI Chatbot

This is an interactive chatbot that leverages AI and Knowledge Graphs to provide information on nutritional supplements

## Steps
- Run Neo4j Knowledge graph (additional information outlined in the knowledge_graph directory)
- Run the Agent

## Run Neo4j
```bash
cd knowledge_graph
docker compose up -d
```

Neo4j Browser: http://localhost:7474  
Bolt endpoint: `bolt://localhost:7687`  
Auth: `neo4j / neo4jpassword`

## Load KG
```bash
docker exec -it supplements-kg   cypher-shell -u neo4j -p neo4jpassword   -f /var/lib/neo4j/import/setup.cypher
```

## Run Agent

First, ensure that the required pacakges are installed
```bash
cd chatbot
pip install -r requirements.txt
```

Then, run the agent using the following command

```bash
streamlit run supplementsrx_chatbot.py
```


## Note
- Ensure that the .env file within the agent directory contains your Google Gemini API key
