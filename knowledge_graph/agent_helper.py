from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4jpassword")

driver = GraphDatabase.driver(URI, auth=AUTH)

def run(q, params=None):
    with driver.session() as s:
        return s.run(q, params or {}).data()

print(run("""
MATCH (s:Supplement)-[r:TREATS]->(c:Condition)
RETURN s.id AS supplement_id, c.id AS condition_id
LIMIT 5
"""))

driver.close()