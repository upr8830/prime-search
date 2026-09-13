"""The OpenAPI schema task 2.5 generates `ui/src/types.ts` from (docs/07 §8).

An endpoint without a response model reaches the UI as `unknown`, and the drift shows up
only in the browser. This pins docs/07 §7's endpoint table and a typed 200 on each.
"""

from __future__ import annotations

from prime_search.api import main

ENDPOINTS = {
    ("/run", "post"),
    ("/run/{run_id}/events", "get"),
    ("/runs", "get"),
    ("/runs/{run_id}", "get"),
    ("/runs/{run_id}/events", "get"),
    ("/docs/{run_id}/{doc_id}", "get"),
    ("/feedback", "post"),
    ("/ui-event", "post"),
    ("/bench/questions", "get"),
    ("/bench/summary", "get"),
}


def test_the_endpoints_are_docs_07s_table() -> None:
    spec = main.app.openapi()
    assert {(path, method) for path, methods in spec["paths"].items() for method in methods} == ENDPOINTS


def test_every_json_endpoint_has_a_typed_response() -> None:
    spec = main.app.openapi()
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            content = operation["responses"]["200"]["content"]
            if path == "/run/{run_id}/events":
                assert "text/event-stream" in content
                continue
            schema = content["application/json"]["schema"]
            if schema.get("type") == "array":
                assert "$ref" in schema["items"], (path, method, schema)
            elif path == "/bench/summary":
                assert schema.get("type") == "object"  # eval.report's JSON, documented in 05 §3
            else:
                assert "$ref" in schema, (path, method, schema)
