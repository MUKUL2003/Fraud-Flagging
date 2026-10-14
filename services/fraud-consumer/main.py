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
TOPIC = os.environ.get("TOPIC_RAW", "transactions.raw")
PUBLISH_TIMEOUT_S = 10  

class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    transaction_id: UUID
    account_id: Annotated[str, StringConstraints(min_length=1)]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    merchant: Annotated[str, StringConstraints(min_length=1)]
    timestamp: AwareDatetime

producer: Producer | None = None
stop_polling = threading.Event()


def poll_forever(p: Producer) -> None:
    while not stop_polling.is_set():
        p.poll(0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global producer
    producer = Producer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "client.id": "transaction-api",
            "acks": "all",  
            "enable.idempotence": True,  
            "message.timeout.ms": 5000,  
        }
    )
    poller = threading.Thread(target=poll_forever, args=(producer,), daemon=True)
    poller.start()
    yield
    stop_polling.set()
    poller.join()
    producer.flush(5)


app = FastAPI(title="transaction-api", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/transactions", status_code=202)
def create_transaction(txn: Transaction):
    payload = txn.model_dump(mode="json")
    # pydantic writes Decimal as a string; the schema says amount is a number.
    payload["amount"] = float(txn.amount)
    value = json.dumps(payload).encode()
    key = txn.account_id.encode()  # partition key = account_id (guide)

    done = threading.Event()
    result: dict = {}

    def on_delivery(err, msg):  # runs in the poller thread
        if err is None:
            result["partition"] = msg.partition()
            result["offset"] = msg.offset()
        result["err"] = err
        done.set()

    try:
        producer.produce(TOPIC, key=key, value=value, on_delivery=on_delivery)
    except (BufferError, KafkaException):
        raise HTTPException(status_code=503, detail="Kafka unavailable")

    # Return 202 only after the broker confirmed the write.
    if not done.wait(PUBLISH_TIMEOUT_S) or result.get("err") is not None:
        raise HTTPException(status_code=503, detail="Kafka did not confirm the write")

    return {
        "status": "accepted",
        "transaction_id": str(txn.transaction_id),
        "partition": result["partition"],
        "offset": result["offset"],
    }