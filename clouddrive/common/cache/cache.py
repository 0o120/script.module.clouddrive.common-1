#-------------------------------------------------------------------------------
# Copyright (C) 2017 Carlos Guzman (cguZZman) carlosguzmang@protonmail.com
# 
# This file is part of Cloud Drive Common Module for Kodi
# 
# Cloud Drive Common Module for Kodi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Cloud Drive Common Module for Kodi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import datetime
import sqlite3
import time

from clouddrive.common.ui.logger import Logger
from clouddrive.common.ui.utils import KodiUtils


class Cache(object):
    _addonid = None
    _name = None
    _expiration = None
    _monitor = None
    _abort = False

    def __init__(self, addonid, name, expiration):
        self._addonid = addonid
        self._name = name
        self._expiration = expiration
        self._monitor = KodiUtils.get_system_monitor()
        self.cleanup()
    
    def __del__(self):
        self._abort = True
        del self._monitor
    
    def _get_connection(self):
        profile_path = KodiUtils.get_addon_info("profile", self._addonid)
        if not KodiUtils.file_exists(profile_path):
            KodiUtils.mkdirs(profile_path)
        db = KodiUtils.translate_path("%s/cache_%s.db" % (profile_path, self._name,))
        con = sqlite3.connect(db, timeout=30, isolation_level=None)
        rs = con.execute("select name from sqlite_master where type='table' AND name='cache'")
        if not rs.fetchone():
            try:
                con.execute("create table cache(key text unique, value text, expiration integer)")
            except Exception as ex:
                Logger.debug(ex)
        return con

    def _get_datetime(self, ts):
        return int(time.mktime(ts.timetuple()))

    def get(self, key):
        row = self._read(key)
        if row and row[1] > self._get_datetime(datetime.datetime.now()):
            return eval(row[0])
        return

    def set(self, key, value):
        expiration = self._get_datetime(datetime.datetime.now() + self._expiration)
        self._insert(key, value, expiration)
        
    def remove(self, key):
        self._execute_sql("delete from cache where key = ?", (key,))
    
    def clear(self):
        self._execute_sql("delete from cache")

    def _read(self, key):
        rs = self._execute_sql("select value, expiration from cache where key = ?", (key,))
        return rs.fetchone()
        
    def _insert(self, key, value, expiration):
        self._execute_sql("insert or replace into cache(key, value, expiration) values(?,?,?)", (key, repr(value), expiration,))
        
    def cleanup(self):
        now = self._get_datetime(datetime.datetime.now())
        self._execute_sql("delete from cache where expiration < ?", (now,))
    
    def _execute_sql(self, query, data=None):
        with self._get_connection() as con:
            retries = 0
            error = None
            while not retries == 10:
                if self._abort:
                    return None
                try:
                    if data:
                        result = con.execute(query, data)
                    else:
                        result = con.execute(query)
                    return result
                except sqlite3.OperationalError as error:
                    if "_database is locked" in error:
                        retries += 1
                        Logger.warning("Cache query retrying #d [%s]: %s" % (retries, query, str(data),))
                        self._monitor.waitForAbort(0.5)
                    else:
                        break
                except Exception as error:
                    break
            Logger.error("Error executing cache query [%s]: %s" % (query, str(error),))
        return None
