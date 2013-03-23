# -*- coding: utf-8 -*-

import json
import os.path

from sqlalchemy import engine_from_config

from .models import (
    Base,
    Session
)


def initialize():
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        u'config.json'
    )
    with open(config_path, u'r') as f:
        config = json.load(f)

    engine = engine_from_config(config[u'sqlalchemy'], prefix=u'')
    Base.metadata.create_all(engine)
    Session.configure(bind=engine)
