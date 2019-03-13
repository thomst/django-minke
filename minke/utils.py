# -*- coding: utf-8 -*-
from __future__ import unicode_literals


def item_by_attr(list, attr, value, default=None):
    return next((i for i in list if hasattr(i, attr) and getattr(i, attr) == value), default)
