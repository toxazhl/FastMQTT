import asyncio
import logging
from typing import TYPE_CHECKING, Any

from .connectors import BaseConnector
from .exceptions import FastMqttError
from .properties import PublishProperties
from .subscription_manager import Subscription, SubscriptionManager
from .types import Message, MessageWithClient

if TYPE_CHECKING:
    from .fastmqtt import FastMqtt

log = logging.getLogger(__name__)


class MessageHandler:
    def __init__(
        self,
        fastmqtt: "FastMqtt",
        connector: BaseConnector,
        subscription_manager: SubscriptionManager,
    ):
        self._fastmqtt = fastmqtt
        self._connector = connector
        self._subscription_manager = subscription_manager

        self._connector.add_message_callback(self.on_message)

    async def on_message(self, message: Message) -> None:
        if message.properties.subscription_identifier is None:
            log.warning(f"Message has no subscription_identifier {message}")
            return

        for id_ in message.properties.subscription_identifier:
            subscription = self._subscription_manager.get_subscription(id_)

            if subscription is None:
                log.error(f"Message has unknown subscription_identifier {id_} ({message.topic})")
                continue

            asyncio.create_task(self._process_message(subscription, message))

    async def _handle_result(self, result: Any, message: Message) -> None:
        if result is None:
            return

        if message.properties.response_topic is None:
            raise FastMqttError("Callback returned result, but message has no response_topic")

        response_properties = None
        if message.properties.correlation_data is not None:
            response_properties = PublishProperties(
                correlation_data=message.properties.correlation_data
            )

        await self._fastmqtt.publish(
            topic=message.properties.response_topic,
            payload=result,
            properties=response_properties,
        )

    async def _process_message(self, subscription: Subscription, message: Message) -> None:
        message_with_client = MessageWithClient(
            topic=message.topic,
            payload=message.payload,
            qos=message.qos,
            retain=message.retain,
            mid=message.mid,
            properties=message.properties,
            client=self._fastmqtt,
        )

        callback_tasks = (
            asyncio.create_task(callback(message_with_client))
            for callback in subscription.callbacks
        )
        for result in asyncio.as_completed(callback_tasks):
            try:
                result = await result
            except Exception as e:
                log.exception(f"Error in callback {e}")
                continue

            await self._handle_result(result, message)
