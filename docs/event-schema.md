# Event Schema

The contract between services. Kafka stores bytes and does not validate them, so
every producer and consumer must follow this document.

Format: JSON, no schema registry (chosen for simplicity and readability in kcat;
at larger scale, move to Avro/Protobuf with a registry for enforced compatibility).

## 1. transactions.raw

Produced by: transaction-api
Consumed by: fraud-consumer
Message key: `account_id`

Why the key matters: Kafka guarantees order only within a partition. Keying by
`account_id` sends all of an account's transactions to the same partition, in
order, which the velocity rule depends on.

Example:

```json
{
  "transaction_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "account_id": "acc_1001",
  "amount": 10000.00,
  "currency": "INR",
  "merchant": "ExampleMart",
  "timestamp": "2026-10-03T18:30:00Z"
}
```

| Field | Type | Rules | Used for |
|---|---|---|---|
| transaction_id | string | UUID, supplied by the client | Postgres primary key; idempotency |
| account_id | string | non-empty | Kafka partition key; velocity rule |
| amount | number | greater than 0 | Amount-threshold rule |
| currency | string | 3 uppercase letters (ISO 4217), e.g. INR | Stored with the record |
| merchant | string | non-empty | Blocklist rule |
| timestamp | string | ISO 8601, UTC, e.g. 2026-10-03T18:30:00Z | Event time; latency measurement |

All six fields are required. Unknown extra fields are rejected.

### Design notes

- **Client-supplied transaction_id.** If a client retries a request, it sends the
  same ID, so `INSERT ... ON CONFLICT DO NOTHING` drops the duplicate. If the API
  generated the ID, a retry would create a genuinely new record.
- **amount as a JSON number.** Floating point is risky for money (0.1 + 0.2 is not
  exactly 0.3). Real systems use integer minor units (paise/cents) or decimals.
  Accepted here for a practice project; the production fix is integer minor units.
- **timestamp is client-supplied event time**, not the time Kafka received it.

## 2. transactions.flagged

Produced by: fraud-consumer
Consumed by: notification-consumer (its own consumer group)
Message key: `account_id`

The original transaction fields plus:

| Field | Type | Rules |
|---|---|---|
| flags | array of string | one or more of HIGH_AMOUNT, HIGH_VELOCITY, BLOCKED_MERCHANT |

## 3. transactions.dlq

Produced by: fraud-consumer
Purpose: malformed messages go here instead of blocking the partition.

| Field | Type | Meaning |
|---|---|---|
| original_payload | string | the raw message exactly as received |
| error | string | why validation failed |
| source_topic | string | topic it came from |
| source_partition | integer | partition it came from |
| source_offset | integer | offset it came from |

A message is malformed if it is not valid JSON, is missing a required field,
has a wrong type, or breaks a rule in section 1 (for example, a negative amount).

## 4. Fraud rules (rule-based only, no ML)

| Flag | Condition |
|---|---|
| HIGH_AMOUNT | amount is at or above above the threshold (configurable, default 10000) |
| HIGH_VELOCITY | more than 5 transactions for the account in 60 s (Redis INCR + EXPIRE) |
| BLOCKED_MERCHANT | merchant is on the blocklist |
Boundary: an amount of exactly 10000 is flagged; 9999.99 is not.

A transaction can carry more than one flag.s