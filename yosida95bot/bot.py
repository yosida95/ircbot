# -*- coding: utf-8 -*-

import functools
import logging
import re
import ssl

from irc.bot import SingleServerIRCBot
from irc.connection import Factory

from .models import (
    Session,
    Message,
    UserGrade
)

logging.basicConfig(level=logging.INFO)


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
        logging.info(u'Welcome message received.')
        for channel in self._channels:
            logging.info(u'Joining to channel named %s' % channel)
            connection.join(channel)

    def on_nicknameinuse(self, connection, event):
        logging.info(u'nickname %s was used' % connection.get_nickname())
        connection.nick(connection.get_nickname() + u'_')

    def on_pubmsg(self, connection, event):
        session = Session()
        message = Message(event.target,
                          event.source.nick, event.arguments[0].strip())
        session.add(message)

        logging.info(u'an message received. %s:%s:%s' % (
            message.channel, message.user, message.message
        ))

        for pattern, handlers in self.handlers.items():
            matches = pattern.match(message.message)
            if matches is None:
                continue

            logging.info(u'message matched %s' % pattern.pattern)

            for handler in handlers:
                try:
                    logging.info('calling handler named %s' % handler.__name__)
                    handler(lambda msg: connection.privmsg(event.target, msg),
                            ChannelSpec(event.target,
                                        connection.get_nickname(),
                                        self.channels[event.target].users()),
                            message, matches)
                except BaseException as why:
                    logging.error(repr(why))
                    if len(handlers) is 1:
                        logging.info(
                            u'Removing handlers for %s' % pattern.pattern
                        )
                        self.handlers.pop(pattern)
                    else:
                        logging.info(
                            u'Removing handler named %s' % handler.__name__
                        )
                        handlers.remove(handler)

        try:
            session.commit()
        except BaseException as why:
            logging.error(u'DB session commit failed with exception %r' % why)
            session.rollback()
        finally:
            session.close()

    def on_join(self, connection, event):
        if connection.get_nickname() in self.channels[event.target].opers():
            connection.mode(event.target, u'+o %s' % event.source.nick)

    @classmethod
    def add_handler(cls, _pattern):
        def receiver(handler):
            logging.debug(u'A handler received named %s for %s' % (
                handler.__name__, _pattern
            ))

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

    def __init__(self, channel, nickname, users):
        self.channel = channel
        self.nickname = nickname
        self.users = users

    def __unicode__(self):
        return '%s: %s' % (self.channelr, u', '.join(self.users))

    def __str__(self):
        return self.__unicode__().encode(u'utf-8')


@Yosida95Bot.add_handler(ur'^ping(\s+(.+))?$')
def ping_handler(sender, channel,  message, matches):
    if matches.group(2) is None or matches.group(2) == channel.nickname():
        sender(u'pong')


@Yosida95Bot.add_handler(ur'^(.+)(\+\+|--)$')
def grade_handler(sender, channel, message, matches):
    user = unicode(matches.group(1))
    if user in channel.users:
        session = Session()

        grade = session.query(UserGrade).filter(
            UserGrade.channel == channel.channel,
            UserGrade.user == user
        ).first()
        if grade is None:
            grade = UserGrade(channel.channel, user)
            session.add(grade)

        if matches.group(2) == u'++':
            grade.increment()
        else:
            grade.decrement()

        sender(u'%s: %d' % (user, grade.grade))

        try:
            session.commit()
        except BaseException:
            session.rollback()
        finally:
            session.close()
