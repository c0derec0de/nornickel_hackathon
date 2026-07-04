from neo4j import GraphDatabase
from ..config import settings
from ..ontology import canonical


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        self.driver.close()

    def init_schema(self):
        with self.driver.session() as s:
            s.run("CREATE CONSTRAINT entity_key IF NOT EXISTS "
                  "FOR (n:Entity) REQUIRE (n.name, n.type) IS UNIQUE")

    # ---------- ingest ----------

    def upsert_entity(self, name: str, etype: str, aliases=None, source=None,
                      geo=None, confidence=0.7):
        cname = canonical(name)
        with self.driver.session() as s:
            s.run(
                """
                MERGE (n:Entity {name:$name, type:$type})
                SET n:`%s`,
                    n.aliases = coalesce(n.aliases, []) + $aliases,
                    n.sources = coalesce(n.sources, []) + $sources,
                    n.geo = coalesce($geo, n.geo),
                    n.confidence = $confidence,
                    n.updated_at = datetime()
                """ % etype,
                name=cname, type=etype, aliases=aliases or [],
                sources=[source] if source else [], geo=geo, confidence=confidence,
            )
        return cname

    def upsert_relation(self, src: str, src_type: str, tgt: str, tgt_type: str,
                        rel_type: str, source=None, condition=None, confidence=0.7):
        cs, ct = canonical(src), canonical(tgt)
        props = {"source": source, "confidence": confidence}
        if condition:
            props.update({
                "cond_quantity": condition.get("quantity"),
                "cond_op": condition.get("op"),
                "cond_value": condition.get("value"),
                "cond_value_max": condition.get("value_max"),
                "cond_unit": condition.get("unit"),
            })
        with self.driver.session() as s:
            s.run(
                """
                MERGE (a:Entity {name:$cs, type:$st})
                MERGE (b:Entity {name:$ct, type:$tt})
                MERGE (a)-[r:`%s`]->(b)
                SET r += $props, r.updated_at = datetime()
                """ % rel_type,
                cs=cs, st=src_type, ct=ct, tt=tgt_type, props=props,
            )

    # ---------- query ----------

    def subgraph_for(self, names: list[str], depth: int = 2, limit: int = 60):
        """Подграф вокруг найденных сущностей (обход до depth уровней)."""
        cnames = [canonical(n) for n in names]
        cy = """
        MATCH (n:Entity) WHERE n.name IN $names
        CALL apoc.path.subgraphAll(n, {maxLevel:$depth, limit:$limit})
        YIELD nodes, relationships
        RETURN nodes, relationships
        """
        nodes, edges = {}, []
        with self.driver.session() as s:
            try:
                res = s.run(cy, names=cnames, depth=depth, limit=limit)
            except Exception:
                # fallback без apoc
                res = s.run(
                    """
                    MATCH (n:Entity)-[r]-(m:Entity)
                    WHERE n.name IN $names
                    RETURN collect(distinct n)+collect(distinct m) AS nodes,
                           collect(distinct r) AS relationships
                    """, names=cnames)
            for rec in res:
                for node in rec["nodes"]:
                    nodes[node.element_id] = {
                        "id": node.get("name"),
                        "label": node.get("name"),
                        "type": node.get("type", "Entity"),
                    }
                for rel in rec["relationships"]:
                    edges.append({
                        "source": rel.start_node.get("name"),
                        "target": rel.end_node.get("name"),
                        "type": rel.type,
                    })
        return list(nodes.values()), edges

    def entities_from_sources(self, docs: list[str], limit: int = 40):
        """Сущности, извлечённые из указанных документов — надёжный сид для подграфа."""
        if not docs:
            return []
        with self.driver.session() as s:
            res = s.run(
                """
                MATCH (n:Entity)
                WHERE any(x IN coalesce(n.sources, []) WHERE x IN $docs)
                RETURN n.name AS name LIMIT $limit
                """, docs=docs, limit=limit)
            return [r["name"] for r in res]

    def find_contradictions(self, limit: int = 20):
        with self.driver.session() as s:
            res = s.run(
                """
                MATCH (a:Entity)-[r:CONTRADICTS]->(b:Entity)
                RETURN a.name AS a, b.name AS b,
                       r.source AS src LIMIT $limit
                """, limit=limit)
            return [f"«{r['a']}» противоречит «{r['b']}»"
                    f"{f' ({r['src']})' if r['src'] else ''}" for r in res]

    def find_gaps(self, limit: int = 15):
        """Материалы без связанных экспериментов = потенциальные пробелы."""
        with self.driver.session() as s:
            res = s.run(
                """
                MATCH (m:Material)
                WHERE NOT (m)<-[:USES_MATERIAL]-(:Experiment)
                RETURN m.name AS name LIMIT $limit
                """, limit=limit)
            return [f"Нет экспериментов с материалом «{r['name']}»" for r in res]

    def stats(self):
        with self.driver.session() as s:
            n = s.run("MATCH (n:Entity) RETURN count(n) AS c").single()["c"]
            r = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            by_type = {row["t"]: row["c"] for row in s.run(
                "MATCH (n:Entity) RETURN n.type AS t, count(*) AS c ORDER BY c DESC")}
            return {"nodes": n, "relations": r, "by_type": by_type}

    def wipe(self):
        with self.driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")


neo4j_client = Neo4jClient()
