# -*- coding: utf-8 -*-

import functools
import logging
import re
import ssl
from wsgiref import simple_server

import webob
from jinja2 import (
    Environment,
    PackageLoader
)

from irc.bot import SingleServerIRCBot
from irc.connection import Factory

from .models import (
    Session,
    Message,
    UserGrade
)

logging.basicConfig(level=logging.INFO)

jinja2 = Environment(loader=PackageLoader(u'yosida95bot', u'templates'),
                     autoescape=True, line_statement_prefix=u'#')


class Router(object):

    def __init__(self):
        self.routing_table = {}

    def add_route(self, pattern, view):
        tokens, variables = self._tokenize(pattern)

        table = self.routing_table
        for token in tokens[:-1]:
            if token not in table:
                table[token] = {}
            table = table[token]
        else:
            assert tokens[-1] not in table,\
                u'This pattern is conflict with %s' % table[tokens[-1]][0]
            table[tokens[-1]] = (pattern, variables, view)

    def route(self, path):
        if len(path) > 0 and path[0] == u'/':
            path = path[1:]

        if len(path) > 0 and path[-1] == u'/':
            path = path[:-1]

        matches = [(self.routing_table, [])]
        for token in path.split(u'/'):
            _matches = []
            for table, variables in matches:
                if token in table:
                    _matches.append((table[token], variables))

                for key in filter(
                    lambda key: u'*' in key and (
                        token.find(key[:-1]) is 0
                        or token[token.rfind(key[1:]):] == key[1:]
                    ),
                    table.keys()
                ):
                    _matches.append((
                        table[key],
                        variables + [
                            token if key == u'*'
                            else token[:(len(key) - 1) * -1] if key[0] == u'*'
                            else token[len(key) - 1:]
                        ]
                    ))
            else:
                matches = _matches
        else:
            assert 0 <= len(matches) < 2, u'More than 2 views hits'

            if len(matches) is 1 and u'$' in matches[0][0]:
                route = matches[0][0][u'$']
                return (route[2], dict(zip(route[1], matches[0][1])))
            else:
                return None

    def _tokenize(self, pattern):
        if len(pattern) > 0 and pattern[0] == u'/':
            pattern = pattern[1:]

        if len(pattern) > 0 and pattern[-1] == u'/':
            pattern = pattern[:-1]

        tokens = []
        variables = []
        for _token in pattern.split(u'/'):
            token = []
            variable = []
            depth = 0
            for y in range(len(_token)):
                if _token[y] == u'(':
                    assert depth is 0, u'Over nested'
                    depth += 1
                    token.append(u'*')
                elif _token[y] == u')':
                    assert depth is 1, u'Over nested'
                    variables.append(u''.join(variable))
                    depth -= 1
                else:
                    if depth is 1:
                        variable.append(_token[y])
                        continue
                    token.append(_token[y])
            else:
                assert depth is 0, u'Unbalanced brackets'
                assert 0 <= token.count(u'*') < 2,\
                    u'Count of variable in same directory must be 1'
                assert token.count(u'*') is 0\
                    or u'*' in (token[0], token[-1]),\
                    u'Variable must be located start or end in directory'
                tokens.append(u''.join(token))
        else:
            tokens.append(u'$')

        return (tokens, variables)


class Yosida95Bot(SingleServerIRCBot):
    handlers = {}
    router = Router()

    def __init__(self, nickname, host, port=6667, use_ssl=False, channels=[]):
        self._channels = channels

        if use_ssl:
            connect_factory = Factory(wrapper=ssl.wrap_socket)
        else:
            connect_factory = Factory()

        def __call__(self, environment, response):
            _request = webob.Request(environment)
            _response = webob.Response()

            view = self.route(_request.path_info)
            if isinstance(view, tuple):
                _request.match_dict = view[1]
                view[0](_request, _response)
            else:
                _response.status_int = 404

            return _response(environment, response)
        setattr(self.router.__class__, u'__call__', __call__)
        simple_server.make_server(u'0.0.0.0', 8080, self.router)\
            .serve_forever()

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

    @classmethod
    def add_web_handler(cls, path_pattern):
        def receiver(handler):
            logging.debug(u'A web handler recieved named %s for %s' % (
                handler.__name__, path_pattern
            ))

            cls.router.add_route(path_pattern, handler)

            return handler
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
