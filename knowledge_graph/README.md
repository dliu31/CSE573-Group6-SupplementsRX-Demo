# SupplementsRx Knowledge Graph — Quick Start for Agent Integration

This folder lets anyone set up the KG locally with Docker, load the CSVs, and connect an agent via Neo4j (Bolt).

## Prerequisites
- Docker + Docker Compose

## Run Neo4j
```bash
cd knowledge_graph
docker compose up -d
```

Neo4j Browser: http://localhost:7474  
Bolt endpoint: `bolt://localhost:7687`  
Auth: `neo4j / neo4jpassword`

## Load the KG
```bash
docker exec -it supplements-kg   cypher-shell -u neo4j -p neo4jpassword   -f /var/lib/neo4j/import/setup.cypher
```

## Sanity checks
In Neo4j Browser:
```cypher
MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS n ORDER BY n DESC;
MATCH (s:Supplement) RETURN count(s) AS supplements;
MATCH (c:Condition)  RETURN count(c) AS conditions;

MATCH (s:Supplement)-[r:TREATS]->(c:Condition)
RETURN s.name AS supplement, c.name AS condition
LIMIT 10;
```

## Option A: connect directly from an agent (Neo4j Python driver)
```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j","neo4jpassword"))

def run(q, params=None):
    with driver.session() as s:
        return s.run(q, params or {}).data()

print(run("""
MATCH (s:Supplement)-[r:TREATS]->(c:Condition)
RETURN s.id AS supplement_id, c.id AS condition_id, r.url AS source
LIMIT 5
"""))

driver.close()
```

## Option B: tiny REST wrapper (if the agent prefers HTTP)
```python
from fastapi import FastAPI, Query
from pydantic import BaseModel
from neo4j import GraphDatabase

app = FastAPI()
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j","neo4jpassword"))

class QueryBody(BaseModel):
    cypher: str
    params: dict | None = None

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/treats")
def treats(supplement_id: str = Query(...)):
    q = '''
    MATCH (s:Supplement {id:$sid})-[r:TREATS]->(c:Condition)
    RETURN s.id AS supplement_id, c.id AS condition_id, r.confidence AS confidence, r.url AS url
    ORDER BY coalesce(r.confidence,0) DESC
    '''
    with driver.session() as s:
        return s.run(q, {"sid": supplement_id}).data()

@app.post("/cypher")
def cypher(body: QueryBody):
    with driver.session() as s:
        return s.run(body.cypher, body.params or {}).data()
```

Run:
```bash
pip install fastapi uvicorn neo4j pydantic
uvicorn main:app --reload --port 8000
```
Test:
```
GET http://localhost:8000/health
GET http://localhost:8000/treats?supplement_id=magnesium
```

## Useful Cypher patterns for agents
- Conditions treated by a supplement
```cypher
MATCH (s:Supplement {id:$sid})-[r:TREATS]->(c:Condition)
RETURN c.name AS condition, coalesce(r.confidence,0.0) AS confidence, r.url AS source
ORDER BY confidence DESC, condition
```
- Supplements indicated for a condition
```cypher
MATCH (s:Supplement)-[r:INDICATED_FOR]->(c:Condition {id:$cid})
RETURN s.name AS supplement, coalesce(r.confidence,0.0) AS confidence, r.url AS source
ORDER BY confidence DESC, supplement
```
