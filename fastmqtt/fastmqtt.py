from typing import Any, Callable, Sequence, Type

from aiomqtt.types import PayloadType

from .connectors import AiomqttConnector, BaseConnector
from .message_handler import MessageHandler
from .properties import ConnectProperties, PublishProperties

# from .response import ResponseContext
from .router import MqttRouter
from .subscription_manager import (
    CallbackType,
    Subscription,
    SubscriptionManager,
)
from .types import RetainHandling, SubscribeOptions

WebSocketHeaders = dict[str, str] | Callable[[dict[str, str]], dict[str, str]]


class FastMqtt(MqttRouter):
    def __init__(
        self,
        hostname: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        identifier: str | None = None,
        will=None,
        keepalive=60,
        properties: ConnectProperties | None = None,
        connector_type: Type[BaseConnector] = AiomqttConnector,
        routers: Sequence[MqttRouter] | None = None,
        default_subscribe_options: SubscribeOptions | None = None,
    ):
        super().__init__(default_subscribe_options=default_subscribe_options)
        self._connector = connector_type(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            identifier=identifier,
            will=will,
            keepalive=keepalive,
            properties=properties,
        )
        self._subscription_manager = SubscriptionManager(self._connector)
        self._message_handler = MessageHandler(self, self._connector, self._subscription_manager)
        self._state: dict[str, Any] = {}

        self._connector.add_connect_callback(self.subscribe_all)
        self._routers = routers or []
        for router in self._routers:
            self.include_router(router)

    @property
    def identifier(self) -> str:
        return self._connector._identifier

    def __setitem__(self, key: str, value: Any) -> None:
        self._state[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._state[key]

    def __delitem__(self, key: str) -> None:
        del self._state[key]

    def get(self, key: str, /, default: Any = None) -> Any:
        return self._state.get(key, default)

    async def connect(self) -> None:
        await self._connector.connect()
        await self.subscribe_all()

    async def disconnect(self) -> None:
        await self._connector.disconnect()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.disconnect()

    async def subscribe(
        self,
        callback: CallbackType,
        topic: str,
        qos: int | None = None,
        no_local: bool | None = None,
        retain_as_published: bool | None = None,
        retain_handling: RetainHandling | None = None,
    ) -> Subscription:
        subscription = self._register(
            callback=callback,
            topic=topic,
            qos=qos,
            no_local=no_local,
            retain_as_published=retain_as_published,
            retain_handling=retain_handling,
        )
        if len(subscription.callbacks) == 1:
            # Only subscribe if it's the first callback
            await self._subscription_manager.subscribe(subscription)

        return subscription

    async def subscribe_all(self) -> None:
        self._subscribed = True
        await self._subscription_manager.subscribe_multiple(self._subscriptions)

    async def unsubscribe(self, identifier: int, callback: CallbackType | None = None) -> None:
        await self._subscription_manager.unsubscribe(identifier, callback)

    async def publish(
        self,
        topic: str,
        payload: PayloadType = None,
        qos: int = 0,
        retain: bool = False,
        properties: PublishProperties | None = None,
    ) -> None:
        await self._connector.publish(
            topic=topic,
            payload=payload,
            qos=qos,
            retain=retain,
            properties=properties,
        )

    # def response_context(
    #     self,
    #     response_topic: str,
    #     qos: int = 0,
    #     default_timeout: float | None = 60,
    #     **kwargs,
    # ) -> ResponseContext:
    #     return ResponseContext(
    #         self,
    #         response_topic,
    #         qos,
    #         default_timeout,
    #         **kwargs,
    #     )
