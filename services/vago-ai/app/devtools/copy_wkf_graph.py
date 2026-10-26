import argparse
import hashlib
import json
from pathlib import Path

import neo4j
from dotenv import dotenv_values
from neo4j.time import Date, DateTime, Duration, Time


TEMPORAL_TYPES = {item.__name__: item for item in (Date, DateTime, Time, Duration)}


def _decode(value: object) -> object:
    if isinstance(value, dict) and set(value) == {"__neo4j_type__", "value"}:
        kind = value["__neo4j_type__"]
        if kind not in TEMPORAL_TYPES:
            raise ValueError(f"未知 Neo4j 属性类型：{kind}")
        return TEMPORAL_TYPES[kind].from_iso_format(value["value"])
    if isinstance(value, dict):
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def _copy(tx, nodes: list[dict], edges: list[dict], user_uuid: str, batch: str) -> None:
    for item in nodes:
        result = tx.run(
            "MERGE (copy:WkfMergeTest {vago_user_uuid: $user_uuid, source_element_id: $source_id}) "
            "SET copy += $properties, copy.wkf_labels = $labels, "
            "copy.vago_user_uuid = $user_uuid, copy.source_element_id = $source_id, copy.wkf_batch = $batch "
            "RETURN count(copy) AS total",
            source_id=item["source_id"], user_uuid=user_uuid, batch=batch,
            labels=item["labels"], properties=_decode(item["properties"]),
        ).single()["total"]
        if result != 1:
            raise ValueError(f"源图节点已经变化：{item['source_id']}")
    for item in edges:
        result = tx.run(
            "MATCH (a:WkfMergeTest {vago_user_uuid: $user_uuid, source_element_id: $from_id}) "
            "MATCH (b:WkfMergeTest {vago_user_uuid: $user_uuid, source_element_id: $to_id}) "
            "MERGE (a)-[copy:WKF_MERGE_REL {source_element_id: $source_id}]->(b) "
            "SET copy += $properties, copy.wkf_type = $type, "
            "copy.source_element_id = $source_id, copy.wkf_batch = $batch "
            "RETURN count(copy) AS total",
            source_id=item["source_id"], from_id=item["from_id"],
            to_id=item["to_id"], user_uuid=user_uuid, batch=batch,
            type=item["type"], properties=_decode(item["properties"]),
        ).single()["total"]
        if result != 1:
            raise ValueError(f"源图关系已经变化：{item['source_id']}")


def _verify(tx, source_nodes: list[dict], source_edges: list[dict],
            user_uuid: str, batch: str) -> tuple[int, int]:
    nodes = tx.run(
        "MATCH (n:WkfMergeTest {vago_user_uuid: $user_uuid, wkf_batch: $batch}) "
        "RETURN count(n) AS total", user_uuid=user_uuid, batch=batch,
    ).single()["total"]
    edges = tx.run(
        "MATCH (a:WkfMergeTest {vago_user_uuid: $user_uuid, wkf_batch: $batch})"
        "-[r:WKF_MERGE_REL {wkf_batch: $batch}]->"
        "(b:WkfMergeTest {vago_user_uuid: $user_uuid, wkf_batch: $batch}) "
        "RETURN count(r) AS total", user_uuid=user_uuid, batch=batch,
    ).single()["total"]
    if (nodes, edges) != (len(source_nodes), len(source_edges)):
        raise ValueError(f"图副本核数不一致：{nodes} 节点、{edges} 关系")
    for item in source_nodes:
        copy = tx.run(
            "MATCH (n:WkfMergeTest {vago_user_uuid: $user_uuid, "
            "source_element_id: $source_id, wkf_batch: $batch}) "
            "RETURN properties(n) AS properties",
            user_uuid=user_uuid, source_id=item["source_id"], batch=batch,
        ).single()
        expected = _decode(item["properties"])
        if copy is None or any(copy["properties"].get(key) != value for key, value in expected.items()):
            raise ValueError(f"图副本节点属性与备份不一致：{item['source_id']}")
    for item in source_edges:
        copy = tx.run(
            "MATCH (:WkfMergeTest {vago_user_uuid: $user_uuid})"
            "-[r:WKF_MERGE_REL {source_element_id: $source_id, wkf_batch: $batch}]->"
            "(:WkfMergeTest {vago_user_uuid: $user_uuid}) "
            "RETURN properties(r) AS properties",
            user_uuid=user_uuid, source_id=item["source_id"], batch=batch,
        ).single()
        expected = _decode(item["properties"])
        if copy is None or any(copy["properties"].get(key) != value for key, value in expected.items()):
            raise ValueError(f"图副本关系属性与备份不一致：{item['source_id']}")
    return nodes, edges


def _rollback(tx, user_uuid: str, batch: str) -> None:
    # 只删除同时具有测试图标签、账号和批次标记的副本；原始 wkf 节点没有该标签。
    tx.run(
        "MATCH (n:WkfMergeTest {vago_user_uuid: $user_uuid, wkf_batch: $batch}) "
        "DETACH DELETE n", user_uuid=user_uuid, batch=batch,
    ).consume()


def main() -> None:
    parser = argparse.ArgumentParser(description="复制 wkf 历史图到只带 WkfMergeTest 标签的隔离测试图")
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--user-uuid", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    graph_path = args.backup_dir / "neo4j-graph.json"
    hashes = json.loads((args.backup_dir / "source-hashes.json").read_text(encoding="utf-8"))
    if hashlib.sha256(graph_path.read_bytes()).hexdigest() != hashes["neo4j-graph.json"]:
        raise ValueError("Neo4j 备份哈希不匹配")
    backup = json.loads(graph_path.read_text(encoding="utf-8"))
    config = dotenv_values(args.source_root / ".env")
    driver = neo4j.GraphDatabase.driver(
        config["MEM_NEO4J_URI"], auth=(config["MEM_NEO4J_USER"], config["MEM_NEO4J_PASSWORD"])
    )
    try:
        with driver.session(database=config.get("MEM_NEO4J_DATABASE") or "neo4j") as session:
            if args.rollback:
                session.execute_read(_verify, backup["nodes"], backup["edges"],
                                     args.user_uuid, args.batch_id)
                session.execute_write(_rollback, args.user_uuid, args.batch_id)
                count = (0, 0)
            else:
                session.execute_write(_copy, backup["nodes"], backup["edges"], args.user_uuid, args.batch_id)
                count = session.execute_read(_verify, backup["nodes"], backup["edges"],
                                             args.user_uuid, args.batch_id)
    finally:
        driver.close()
    print(f"隔离测试图核数：{count[0]} 节点、{count[1]} 关系")


if __name__ == "__main__":
    main()
