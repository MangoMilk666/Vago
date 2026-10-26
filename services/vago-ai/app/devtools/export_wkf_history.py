import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

import neo4j
import psycopg
from dotenv import dotenv_values
from neo4j.time import Date, DateTime, Duration, Time


TEMPORAL_TYPES = (Date, DateTime, Time, Duration)


def _encode_graph_value(value: object) -> object:
    if isinstance(value, TEMPORAL_TYPES):
        return {"__neo4j_type__": type(value).__name__, "value": str(value)}
    if isinstance(value, dict):
        return {key: _encode_graph_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_graph_value(item) for item in value]
    return value


def _write_private(path: Path, value: object) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, default=str)


def main() -> None:
    parser = argparse.ArgumentParser(description="备份 wkf 会话、候选和图记忆到私有目录")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve()
    backup = args.backup_dir.resolve()
    if backup.exists():
        raise ValueError("备份目录已经存在，请指定新的导入批次目录")
    backup.mkdir(mode=0o700, parents=True)
    (backup / "sessions").mkdir(mode=0o700)
    (backup / "domain-sessions").mkdir(mode=0o700)

    files = sorted((source / "app/session").glob("session-*.jsonl"))
    snapshots = sorted((source / "app/domain-session").glob("*.json"))
    hashes = {}
    for path in files + snapshots:
        target = backup / ("sessions" if path.suffix == ".jsonl" else "domain-sessions") / path.name
        shutil.copyfile(path, target)
        target.chmod(0o600)
        hashes[str(target.relative_to(backup))] = hashlib.sha256(target.read_bytes()).hexdigest()

    config = dotenv_values(source / ".env")
    # 如果源库无法读取，立即停止；不能将缺失的历史误判为空库。
    with psycopg.connect(config["MEMORY_DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.itinerary_results')")
            if cursor.fetchone()[0] is None:
                raise RuntimeError("wkf PostgreSQL 缺少 itinerary_results 表")
            cursor.execute(
                "SELECT id, chat_id, plan_uuid, version, city, payload, warnings, created_at "
                "FROM public.itinerary_results ORDER BY id"
            )
            columns = [column.name for column in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    _write_private(backup / "postgres-proposals.json", results)

    graph = neo4j.GraphDatabase.driver(
        config["MEM_NEO4J_URI"], auth=(config["MEM_NEO4J_USER"], config["MEM_NEO4J_PASSWORD"])
    )
    try:
        with graph.session(database=config.get("MEM_NEO4J_DATABASE") or "neo4j") as session:
            nodes = session.run(
                "MATCH (n) WHERE NOT n:WkfMergeTest "
                "RETURN elementId(n) AS source_id, labels(n) AS labels, properties(n) AS properties"
            ).data()
            edges = session.run(
                "MATCH (a)-[r]->(b) WHERE NOT a:WkfMergeTest AND NOT b:WkfMergeTest "
                "RETURN elementId(r) AS source_id, elementId(a) AS from_id, "
                "elementId(b) AS to_id, type(r) AS type, properties(r) AS properties"
            ).data()
    finally:
        graph.close()
    _write_private(backup / "neo4j-graph.json", _encode_graph_value({"nodes": nodes, "edges": edges}))
    for name in ("postgres-proposals.json", "neo4j-graph.json"):
        hashes[name] = hashlib.sha256((backup / name).read_bytes()).hexdigest()
    _write_private(backup / "source-hashes.json", hashes)
    print(f"备份完成：会话文件 {len(files)}，领域快照 {len(snapshots)}，PostgreSQL 候选 {len(results)}，图节点 {len(nodes)}，图关系 {len(edges)}")


if __name__ == "__main__":
    main()
