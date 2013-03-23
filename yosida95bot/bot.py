# -*- coding: utf-8 -*-

import functools
import logging
import re
import ssl

from irc.bot import SingleServerIRCBot
from irc.connection import Factory

from .models import (
    Session,
    Message
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler)


class Yosida95Bot(SingleServerIRCBot):
    handlers = {}

    def __init__(self, nickname, host, port=6667, use_ssl=False, channels=[]):
        self._channels = channels

        if use_ssl:
            connect_factory = Factory(wrapper=ssl.wrap_socket)
        else:
            connect_factory = Factory()

        super(Yosida95Bot, self).__init__(
            [(host, port)], nickname, nickname,
            connect_factory=connect_factory
        )

    def on_welcome(self, connection, event):
        for channel in self._channels:
            connection.join(channel)

    def on_nicknameinuse(self, connection, event):
        connection.nick(connection.get_nickname() + u'_')

    def on_pubmsg(self, connection, event):
        session = Session()
        message = Message(event.target,
                          event.source.nick, event.arguments[0].strip())
        session.add(message)

        for pattern, handlers in self.handlers.items():
            matches = pattern.match(message.message)
            if matches is None:
                continue

            for handler in handlers:
                try:
                    handler(lambda msg: connection.privmsg(event.target, msg),
                            ChannelSpec(event.target,
                                        connection.get_nickname(),
                                        self.channels[event.target].users()),
                            message, matches)
                except BaseException as why:
                    logging.error(unicode(why))
                    if len(handlers) is 1:
                        self.handlers.pop(pattern)
                    else:
                        handlers.remove(handler)

        session.commit()
        session.close()

    def on_join(self, connection, event):
        if connection.get_nickname() in self.channels[event.target].opers():
            connection.mode(event.target, u'+o %s' % event.source.nick)

    @classmethod
    def add_handler(cls, _pattern):
        def receiver(handler):
            pattern = re.compile(_pattern, re.UNICODE | re.IGNORECASE)
            if pattern in cls.handlers:
                cls.handlers[pattern].append(handler)
            else:
                cls.handlers[pattern] = [handler]

            @functools.wraps(handler)
            def wrapper(*args, **kwargs):
                return handler(*args, **kwargs)
            return wrapper
        return receiver


class ChannelSpec(object):

    def __init__(self, channel, nick, members):
        self.channel = channel
        self.nick = nick
        self.members = members

    def get_channel(self):
        return self.channel

    def get_nick(self):
        return self.nick

    def get_members(self):
        return self.members

    def __unicode__(self):
        return '%s: %s' % (self.channelr, u', '.join(self.members))

    def __str__(self):
        return self.__unicode__().encode(u'utf-8')


@Yosida95Bot.add_handler(ur'^ping(\s+(.+))?$')
def ping_handler(sender, channel,  message, matches):
    if matches.group(2) is None or matches.group(2) == channel.get_nick():
        sender(u'pong')
