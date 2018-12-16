# -*- coding: utf-8 -*-
from __future__ import unicode_literals


class Printer:
    STATUS_COLORS = dict(
        success = '\033[1;37;42m',
        warning = '\033[1;37;43m',
        error   = '\033[1;37;41m')

    LEVEL_COLORS = dict(
        info    = '\033[32m',
        warning = '\033[33m',
        error   = '\033[31m')

    LEVEL_COLORS_UNDERSCORE = dict(
        info    = '\033[4;32m',
        warning = '\033[4;33m',
        error   = '\033[4;31m')

    CLEAR = '\033[0m'
    CLEAR_FG = '\033[39m'
    WIDTH = 40
    PREFIX_WIDTH = 7
    DELIMITER = ': '

    @classmethod
    def prnt(cls, session):
        player = unicode(session.player).ljust(cls.WIDTH)
        status = session.status.upper().ljust(cls.PREFIX_WIDTH)
        color = cls.STATUS_COLORS[session.status]
        delimiter = cls.DELIMITER
        print color + status + cls.DELIMITER + player + cls.CLEAR

        msgs = list(session.messages.all())
        msg_count = len(msgs)
        for i, msg in enumerate(msgs, start=1):
            underscore = True if i < msg_count else False
            cls.prnt_msg(msg, underscore)

    @classmethod
    def prnt_msg(cls, msg, underscore=False):
        color = cls.LEVEL_COLORS[msg.level]
        level = msg.level.ljust(cls.PREFIX_WIDTH)
        lines = msg.text.splitlines()

        for line in lines[:-1 if underscore else None]:
            print color + level + cls.CLEAR + cls.DELIMITER + line

        if underscore:
            color = cls.LEVEL_COLORS_UNDERSCORE[msg.level]
            line = lines[-1].ljust(cls.WIDTH)
            print color + level + cls.CLEAR_FG + cls.DELIMITER + line + cls.CLEAR
