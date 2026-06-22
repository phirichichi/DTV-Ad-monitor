import json
import logging
from typing import Generator

from app.core.config import get_settings

logger = logging.getLogger("dtv.kafka_consumer")
settings = get_settings()


class KafkaJSONConsumer:
    def __init__(
        self,
        topic: str,
        group_id: str,
        bootstrap_servers: str | None = None,
        client_id: str = "dtv-detection-consumer",
    ):
        self.topic = topic
        self.bootstrap_servers = bootstrap_servers or getattr(
            settings,
            "kafka_bootstrap_servers",
            "kafka:9092",
        )

        from kafka import KafkaConsumer

        self.consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=[
                x.strip()
                for x in self.bootstrap_servers.split(",")
                if x.strip()
            ],
            group_id=group_id,
            client_id=client_id,
            enable_auto_commit=True,
            auto_offset_reset="latest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            max_poll_records=50,
        )

    def iter_messages(self) -> Generator[dict, None, None]:
        logger.info("kafka_consumer_listening topic=%s", self.topic)

        for message in self.consumer:
            yield message.value

    def close(self) -> None:
        self.consumer.close()