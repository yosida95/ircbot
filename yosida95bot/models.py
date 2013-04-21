# -*- coding: utf-8 -*-

from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    Unicode
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import UniqueConstraint

Session = sessionmaker()
Base = declarative_base()


class Message(Base):
    __tablename__ = u'message_log'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    channel = Column(Unicode(50), nullable=False)
    user = Column(Unicode(50), nullable=False)
    message = Column(Unicode(512), nullable=False)
    created_at = Column(DateTime(), nullable=False)

    def __init__(self, channel, user, message):
        self.channel = channel
        self.user = user
        self.message = message
        self.created_at = datetime.utcnow()

    def __unicode__(self):
        return '%s: %s' % (self.sender, self.text)

    def __str__(self):
        return self.__unicode__().encode(u'utf-8')


class UserGrade(Base):
    __tablename__ = u'user_grade'
    __table_args__ = (
        UniqueConstraint(u'channel', u'user'),
    )

    id = Column(Integer(), primary_key=True, autoincrement=True)
    channel = Column(Unicode(50), nullable=False)
    user = Column(Unicode(50), nullable=False)
    grade = Column(Integer(), nullable=False)

    def __init__(self, channel, user):
        self.channel = channel
        self.user = user
        self.grade = 0

    def increment(self):
        self.grade += 1

    def decrement(self):
        self.grade -= 1

    def __unicode__(self):
        return '%s<%s>: %d' % (self.user, self.channel, self.grade)

    def __str__(self):
        return self.__unicode__().encode(u'utf-8')
