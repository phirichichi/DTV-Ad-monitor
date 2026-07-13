#backend/app/infrastructure/messaging/kafka_producer.py
import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("dtv.kafka_producer")
settings = get_settings()

class KafkaJSONProducer:
    def __init__(
        self,
        bootstrap_servers: str | None = None,
        client_id: str = "dtv-ingestion-producer",
    ):
        self.bootstrap_servers = bootstrap_servers or getattr(
            settings,
            "kafka_bootstrap_servers",
            "kafka:9092",
        )
        from kafka import KafkaProducer

        self.producer = KafkaProducer(
            bootstrap_servers=[x.strip() for x in self.bootstrap_servers.split(",") if x.strip()],
            client_id=client_id,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else None,
            acks="all",
            retries=5,
            linger_ms=50,
            max_in_flight_requests_per_connection=5,
        )

    def publish(self, topic: str, payload: dict[str, Any], key: str | None = None) -> None:
        future = self.producer.send(topic, key=key, value=payload)
        metadata = future.get(timeout=10)
        logger.info(
            "kafka_publish_success topic=%s partition=%s offset=%s",
            metadata.topic,
            metadata.partition,
            metadata.offset,
        )

    def flush(self) -> None:
        self.producer.flush()

    def close(self) -> None:
        try:
            self.producer.flush()
        finally:
            self.producer.close()