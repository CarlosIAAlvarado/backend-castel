from fastapi import APIRouter, HTTPException
from app.config.database import database_manager
from app.infrastructure.utils.data_normalizer import normalizer
from typing import Dict, Any, List
from datetime import datetime

router = APIRouter(prefix="/api/exploration", tags=["Data Exploration"])


@router.get("/balances/sample")
def get_balances_sample(limit: int = 5) -> Dict[str, Any]:
    try:
        collection = database_manager.get_collection("balances")

        total_count = collection.count_documents({})

        sample_docs = list(collection.find().limit(limit))

        for doc in sample_docs:
            doc["_id"] = str(doc["_id"])

        fields = list(sample_docs[0].keys()) if sample_docs else []

        return {
            "collection": "balances",
            "total_documents": total_count,
            "sample_size": len(sample_docs),
            "fields": fields,
            "sample_data": sample_docs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/movements/sample")
def get_movements_sample(limit: int = 5) -> Dict[str, Any]:
    try:
        collection = database_manager.get_collection("mov07.10")

        total_count = collection.count_documents({})

        sample_docs = list(collection.find().limit(limit))

        for doc in sample_docs:
            doc["_id"] = str(doc["_id"])

        fields = list(sample_docs[0].keys()) if sample_docs else []

        return {
            "collection": "mov07.10",
            "total_documents": total_count,
            "sample_size": len(sample_docs),
            "fields": fields,
            "sample_data": sample_docs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balances/date-range")
def get_balances_date_range() -> Dict[str, Any]:
    try:
        collection = database_manager.get_collection("balances")

        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "min_date": {"$min": "$createdAt"},
                    "max_date": {"$max": "$createdAt"}
                }
            }
        ]

        result = list(collection.aggregate(pipeline))

        if result:
            return {
                "collection": "balances",
                "min_date": result[0]["min_date"],
                "max_date": result[0]["max_date"]
            }
        else:
            return {
                "collection": "balances",
                "message": "No data found"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/movements/date-range")
def get_movements_date_range() -> Dict[str, Any]:
    try:
        collection = database_manager.get_collection("mov07.10")

        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "min_date": {"$min": "$updatedTime"},
                    "max_date": {"$max": "$updatedTime"}
                }
            }
        ]

        result = list(collection.aggregate(pipeline))

        if result:
            return {
                "collection": "mov07.10",
                "min_date": result[0]["min_date"],
                "max_date": result[0]["max_date"]
            }
        else:
            return {
                "collection": "mov07.10",
                "message": "No data found"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balances/stats")
def get_balances_stats() -> Dict[str, Any]:
    try:
        collection = database_manager.get_collection("balances")

        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_documents": {"$sum": 1},
                    "unique_users": {"$addToSet": "$userId"},
                    "avg_balance": {"$avg": "$balance"},
                    "min_balance": {"$min": "$balance"},
                    "max_balance": {"$max": "$balance"}
                }
            }
        ]

        result = list(collection.aggregate(pipeline))

        if result:
            stats = result[0]
            return {
                "collection": "balances",
                "total_documents": stats["total_documents"],
                "unique_users": len(stats["unique_users"]),
                "avg_balance": stats["avg_balance"],
                "min_balance": stats["min_balance"],
                "max_balance": stats["max_balance"]
            }
        else:
            return {
                "collection": "balances",
                "message": "No data found"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/movements/stats")
def get_movements_stats() -> Dict[str, Any]:
    try:
        collection = database_manager.get_collection("mov07.10")

        all_docs = list(collection.find())

        if not all_docs:
            return {
                "collection": "mov07.10",
                "message": "No data found"
            }

        unique_users = set()
        unique_symbols = set()
        pnl_values = []

        for doc in all_docs:
            if "user" in doc:
                unique_users.add(doc["user"])

            if "symbol" in doc:
                unique_symbols.add(doc["symbol"])

            if "closedPnl" in doc:
                pnl = normalizer.normalize_pnl(doc["closedPnl"])
                pnl_values.append(pnl)

        total_pnl = sum(pnl_values)
        avg_pnl = total_pnl / len(pnl_values) if pnl_values else 0
        min_pnl = min(pnl_values) if pnl_values else 0
        max_pnl = max(pnl_values) if pnl_values else 0

        return {
            "collection": "mov07.10",
            "total_documents": len(all_docs),
            "unique_users": len(unique_users),
            "unique_symbols": len(unique_symbols),
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "min_pnl": min_pnl,
            "max_pnl": max_pnl
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/normalize-pnl")
def test_normalize_pnl() -> Dict[str, Any]:
    test_cases = [
        "8,43187779",
        "-14,7318102",
        "123.45",
        "-67.89",
        123,
        -456,
        None,
        ""
    ]

    results = []
    for test in test_cases:
        normalized = normalizer.normalize_pnl(test)
        results.append({
            "original": test,
            "normalized": normalized,
            "type": type(normalized).__name__
        })

    return {
        "test": "PnL Normalization",
        "results": results
    }


@router.get("/test/normalize-dates")
def test_normalize_dates() -> Dict[str, Any]:
    test_cases = [
        "2025-10-07T05:00:10.065Z",
        "2025-10-07 10:32:43",
        "2025-05-28T01:34:01.502Z"
    ]

    results = []
    for test in test_cases:
        normalized = normalizer.normalize_datetime(test)
        results.append({
            "original": test,
            "normalized": normalized.isoformat() if normalized else None,
            "timezone": str(normalized.tzinfo) if normalized else None
        })

    return {
        "test": "Date Normalization",
        "timezone_target": "America/Bogota",
        "results": results
    }
