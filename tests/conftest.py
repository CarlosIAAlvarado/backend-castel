import pytest
from datetime import datetime
from typing import List, Dict, Any

@pytest.fixture
def sample_balance_data() -> List[Dict[str, Any]]:
    return [
        {
            "date": datetime(2024, 1, 1),
            "account": "ACC001",
            "agent_id": "agent_1",
            "balance": 10000.0
        },
        {
            "date": datetime(2024, 1, 1),
            "account": "ACC002",
            "agent_id": "agent_2",
            "balance": 15000.0
        }
    ]

@pytest.fixture
def sample_movement_data() -> List[Dict[str, Any]]:
    return [
        {
            "date": datetime(2024, 1, 1),
            "account": "ACC001",
            "pnl": 500.0,
            "commission": 10.0
        },
        {
            "date": datetime(2024, 1, 1),
            "account": "ACC002",
            "pnl": -200.0,
            "commission": 5.0
        }
    ]

@pytest.fixture
def sample_agent_metrics() -> List[Dict[str, Any]]:
    return [
        {
            "agent_id": "agent_1",
            "total_aum": 50000.0,
            "roi_7d": 5.5,
            "roi_30d": 12.3,
            "num_accounts": 3
        },
        {
            "agent_id": "agent_2",
            "total_aum": 75000.0,
            "roi_7d": 8.2,
            "roi_30d": 15.7,
            "num_accounts": 5
        },
        {
            "agent_id": "agent_3",
            "total_aum": 30000.0,
            "roi_7d": -2.1,
            "roi_30d": 3.4,
            "num_accounts": 2
        }
    ]
