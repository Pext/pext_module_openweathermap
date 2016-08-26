#!/usr/bin/env python3

# Copyright (C) 2016 Sylvia van Os <iamsylvie@openmailbox.org>
# Pext openweathmap module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import time
from urllib.request import urlopen
from urllib.error import URLError

from pext_base import ModuleBase
from pext_helpers import Action


class Module(ModuleBase):
    def init(self, settings, q):
        self.key = "c98d3515966557887e4e0c5b656b7001" if ("key" not in settings) else settings['key']
        self.q = q

        self.entries = {}
        self.cachedCities = {}

        self.scriptLocation = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        
        self._getEntries()

    def _getEntries(self):
        with open(os.path.join(self.scriptLocation, 'city.list.json')) as f:
            for line in f:
                city = json.loads(line)
                formattedCity = "{} ({})".format(city['name'], city['country'])
                self.entries[formattedCity] = city
        
        # While this goes against Pext's module development recommendation to
        # at least show some entries as soon as possible, appending a list of
        # this size using Action.addEntry one-by-one is simply too slow
        self.q.put([Action.replaceEntryList, list(self.entries.keys())])

    def stop(self):
        pass

    def selectionMade(self, selection):
        if len(selection) == 0:
            self.q.put([Action.replaceEntryList, list(self.entries.keys())])
        elif len(selection) == 1:
            cityId = self.entries[selection[0]]['_id']

            # Use cache for 10 minutes
            if cityId in self.cachedCities and self.cachedCities[cityId]["time"] > time.time() - 600:
                self.q.put([Action.replaceEntryList, self.cachedCities[cityId]["data"]])
                return
        
            try:
                httpResponse = urlopen("http://api.openweathermap.org/data/2.5/weather?id={}&appid={}".format(cityId, self.key))
            except URLError as e:
                self.q.put([Action.addError, "Failed to request weather data: {}".format(e)])
                self.q.put([Action.setSelection, []])
                return

            responseData = httpResponse.read().decode("utf-8") 
            try:
                data = json.loads(responseData)
            except json.JSONDecodeError as e:
                self.q.put([Action.addError, "Failed to decode weather data: {}".format(e)])
                self.q.put([Action.setSelection, []])
                return

            cache = {'time': time.time(), 'data': []}
            cache["data"].append("{} ({})".format(data['name'], data["sys"]["country"]))
            cache["data"].append("{:.2f} °C / {:.2f} °F".format(data["main"]["temp"] - 273.15, data["main"]["temp"] * 9 / 5 - 459.67))
            cache["data"].append(data["weather"][0]["description"].capitalize())
            self.cachedCities[cityId] = cache
            self.q.put([Action.replaceEntryList, cache["data"]])
        else:
            self.q.put([Action.copyToClipboard, selection[1]])
            self.q.put([Action.close])

    def runCommand(self, command, printOnSuccess=False, hideErrors=False):
        pass

    def processResponse(self, response):
        pass
