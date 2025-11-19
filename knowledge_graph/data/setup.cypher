CREATE CONSTRAINT IF NOT EXISTS FOR (s:Supplement) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Condition)  REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (src:Source)   REQUIRE src.id IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///nodes_supplements.csv' AS row
WITH trim(row.supplement_id) AS sid, trim(row.supplement_name) AS sname, trim(row.entity_type) AS et
WHERE sid IS NOT NULL AND sid <> ''
MERGE (s:Supplement {id: sid})
SET s.name = coalesce(sname, s.name),
    s.entity_type = CASE WHEN et IS NOT NULL AND et <> '' THEN et ELSE s.entity_type END;

LOAD CSV WITH HEADERS FROM 'file:///nodes_conditions.csv' AS row
WITH trim(row.condition_id) AS cid, trim(row.condition_name) AS cname, trim(row.entity_type) AS et
WHERE cid IS NOT NULL AND cid <> ''
MERGE (c:Condition {id: cid})
SET c.name = coalesce(cname, c.name),
    c.entity_type = CASE WHEN et IS NOT NULL AND et <> '' THEN et ELSE c.entity_type END;

LOAD CSV WITH HEADERS FROM 'file:///edges_relationships.csv' AS row
WITH toUpper(trim(row.type)) AS t, trim(row.supplement_id) AS sid, trim(row.condition_id) AS cid, trim(row.url) AS url
WHERE sid <> '' AND cid <> '' AND t IN ['TREATS','INDICATED_FOR']
MATCH (s:Supplement {id: sid}), (c:Condition {id: cid})
FOREACH (_ IN CASE WHEN t='TREATS' THEN [1] ELSE [] END |
  MERGE (s)-[r:TREATS]->(c) SET r.url = coalesce(url, r.url)
)
FOREACH (_ IN CASE WHEN t='INDICATED_FOR' THEN [1] ELSE [] END |
  MERGE (s)-[r:INDICATED_FOR]->(c) SET r.url = coalesce(url, r.url)
);

LOAD CSV WITH HEADERS FROM 'file:///edges_detailed.csv' AS row
WITH trim(row.supplement_id) AS sid, trim(row.relation_type) AS rt, trim(row.supplement_name) AS sname,
     trim(row.condition_id) AS cid, toFloat(row.confidence) AS conf,
     trim(row.extraction_method) AS method, trim(row.source_url) AS srcurl, row.evidence_text AS evidence
WHERE sid <> '' AND cid <> '' AND rt IN ['TREATS','INDICATED_FOR']
MATCH (s:Supplement {id: sid}), (c:Condition {id: cid})
FOREACH (_ IN CASE WHEN rt='TREATS' THEN [1] ELSE [] END |
  MERGE (s)-[r:TREATS]->(c)
  SET r.confidence = coalesce(conf, r.confidence),
      r.extraction_method = coalesce(method, r.extraction_method),
      r.evidence_text = coalesce(evidence, r.evidence_text),
      r.url = coalesce(srcurl, r.url)
)
FOREACH (_ IN CASE WHEN rt='INDICATED_FOR' THEN [1] ELSE [] END |
  MERGE (s)-[r:INDICATED_FOR]->(c)
  SET r.confidence = coalesce(conf, r.confidence),
      r.extraction_method = coalesce(method, r.extraction_method),
      r.evidence_text = coalesce(evidence, r.evidence_text),
      r.url = coalesce(srcurl, r.url)
);

LOAD CSV WITH HEADERS FROM 'file:///edges_detailed.csv' AS row
WITH trim(row.source_url) AS srcurl
WHERE srcurl IS NOT NULL AND srcurl <> ''
MERGE (src:Source {id: srcurl})
SET src.url = srcurl;

MATCH (s:Supplement)-[r]->(c:Condition)
RETURN type(r) AS rel, count(*) AS n
ORDER BY n DESC
LIMIT 10;
