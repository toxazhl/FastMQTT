import logging
from typing import Any, Callable

import aiomqtt

from .subscription_manager import (
    CallbackType,
    Retain,
    Subscription,
)

log = logging.getLogger(__name__)


class MQTTRouter:
    def __init__(self):
        self.subscriptions: list[Subscription] = []

    def _check_different(self, subscription: Subscription, **new_attrs) -> None:
        for name, value in new_attrs.items():
            exist_sub_attr = getattr(subscription, name)

            if exist_sub_attr != value:
                log.warning(
                    "Subscription %s has different %s. Existing: %s, New: %s",
                    subscription.topic,
                    name,
                    exist_sub_attr,
                    value,
                )

    def register(
        self,
        callback: CallbackType,
        topic: str,
        qos: int = 0,
        no_local: bool = False,
        retain_as_published: bool = False,
        retain_handling: Retain = Retain.SEND_ON_SUBSCRIBE,
    ) -> Subscription:
        for subscription in self.subscriptions:
            if str(subscription.topic) == topic:
                subscription.callbacks.append(callback)
                self._check_different(
                    subscription,
                    qos=qos,
                    no_local=no_local,
                    retain_as_published=retain_as_published,
                    retain_handling=retain_handling,
                )
                return subscription

        subscription = Subscription(
            [callback],
            aiomqtt.Topic(topic),
            qos,
            no_local,
            retain_as_published,
            retain_handling,
        )

        self.subscriptions.append(subscription)

        return subscription

    def on_message(
        self,
        topic: str,
        qos: int = 0,
        no_local: bool = False,
        retain_as_published: bool = False,
        retain_handling: Retain = Retain.SEND_ON_SUBSCRIBE,
    ) -> Callable[..., Any]:
        def wrapper(callback: CallbackType) -> CallbackType:
            self.register(
                callback,
                topic,
                qos,
                no_local,
                retain_as_published,
                retain_handling,
            )
            return callback

        return wrapper
