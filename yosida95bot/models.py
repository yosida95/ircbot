# -*- coding: utf-8 -*-

import uuid
from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column,
    DateTime,
    Unicode
)
from sqlalchemy.orm import sessionmaker

Session = sessionmaker()
Base = declarative_base()


class Message(Base):
    __tablename__ = u'message_log'

    id = Column(Unicode(32), nullable=False, primary_key=True)
    channel = Column(Unicode(50), nullable=False)
    nickname = Column(Unicode(15), nullable=False)
    message = Column(Unicode(512), nullable=False)
    created_at = Column(DateTime(), nullable=False)

    def __init__(self, channel, nickname, message):
        self.id = uuid.uuid4().hex
        self.channel = channel
        self.nickname = nickname
        self.message = message
        self.created_at = datetime.utcnow()

    def __unicode__(self):
        return '%s: %s' % (self.sender, self.text)

    def __str__(self):
        return self.__unicode__().encode(u'utf-8')
