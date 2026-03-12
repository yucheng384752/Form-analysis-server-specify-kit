from app.services import analytics_external


def test_unified_snapshot_llm_reports_aggregates_station_and_feature(monkeypatch):
    rows = [{"event_id": "20250902_P24_238-2_301", "total_anomalies": 2}]
    raw = [
        {
            "event_id": "20250902_P24_238-2_301",
            "main_anomalies": {
                "total_anomalies": 2,
                "by_station": {
                    "P2": {
                        "anomalies": [
                            {"feature_name": "Burr"},
                            {"feature_name": "Burr"},
                        ]
                    }
                },
            },
        }
    ]

    monkeypatch.setattr(analytics_external, "get_analytics_artifact_list_view", lambda *args, **kwargs: rows)
    monkeypatch.setattr(analytics_external, "load_analytics_artifact", lambda *args, **kwargs: raw)

    out = analytics_external.get_analytics_artifact_unified_snapshot(
        "llm_reports",
        product_ids=["20250902_P24_238-2_301"],
    )

    assert out["artifact_key"] == "llm_reports"
    assert out["sample_count"] == 1
    assert out["metrics"]["total_anomalies"] == 2
    assert {"name": "P2", "count": 2} in out["station_distribution"]
    assert any(x["name"] == "LLM:Burr" and x["count"] == 2 for x in out["top_features"])


def test_unified_snapshot_rag_results_aggregates_station_and_feature(monkeypatch):
    rows = [{"event_id": "20250902_P24_238-2_301", "feature_count": 1, "sop_count": 2}]
    raw = {
        "20250902_P24_238-2_301": {
            "Burr": [
                "C001,P2,Burr,NG,problem,action,sec",
                "C002,P2,Burr,NG,problem,action,sec",
            ]
        }
    }

    monkeypatch.setattr(analytics_external, "get_analytics_artifact_list_view", lambda *args, **kwargs: rows)
    monkeypatch.setattr(analytics_external, "load_analytics_artifact", lambda *args, **kwargs: raw)

    out = analytics_external.get_analytics_artifact_unified_snapshot(
        "rag_results",
        product_ids=["20250902_P24_238-2_301"],
    )

    assert out["artifact_key"] == "rag_results"
    assert out["sample_count"] == 1
    assert out["metrics"]["total_features"] == 1
    assert out["metrics"]["total_sop"] == 2
    assert {"name": "P2", "count": 2} in out["station_distribution"]
    assert any(x["name"] == "RAG:Burr" and x["count"] == 1 for x in out["top_features"])
