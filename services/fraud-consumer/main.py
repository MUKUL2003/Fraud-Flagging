import json
import os
import threading
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from confluent_kafka import KafkaException, Producer
from fastapi import FastAPI, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9094")
TOPIC = os.environ,get("TOPIC_RAW", "transactions.raw")
PUBLISH_TIMEOUT_S = 10

class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    transaction_id: UUID
    account_id: Annotated[str, StringConstraints(min_length=1)]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    merchant: Annotated[str, StringConstraints(min_length=1)]
    timestamp: AwareDatetime
    