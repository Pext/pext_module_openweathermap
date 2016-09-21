#!/usr/bin/env python3

# Copyright (C) 2016 Sylvia van Os <iamsylvie@openmailbox.org>
#
# Pext OpenWeatherMap module is free software: you can redistribute it and/or
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
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError

from pext_base import ModuleBase
from pext_helpers import Action, SelectionType


class Module(ModuleBase):
    def init(self, settings, q):
        self.key = "c98d3515966557887e4e0c5b656b7001" if ("key" not in settings) else settings['key']
        self.baseUrl = "http://api.openweathermap.org/data/2.5"

        self.q = q

        self.entries = {}
        self.cachedCities = {}
        self.cachedForecasts = {}

        self.scriptLocation = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        
        self._setMainCommands()
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

    def _setMainCommands(self):
        self.q.put([Action.setHeader])
        self.q.put([Action.replaceCommandList, ["weather <full city name>",
                                                "forecast <full city name>"]])

    def _getCityId(self, identifier):
        return self.entries[identifier]['_id']

    def _formatData(self, data):
        return [
                   self._formatPlaceName(data),
                   self._formatTemperature(data),
                   self._formatWeatherDescription(data)
               ]

    def _formatPlaceName(self, data):
        return "{} ({})".format(data['name'], data["sys"]["country"])

    def _formatTemperature(self, data):
        kelvin = data["main"]["temp"]
        celcius = kelvin - 273.15
        fahrenheit = kelvin * 9 / 5 - 459.67
        return "{:.2f} °C / {:.2f} °F".format(celcius, fahrenheit)

    def _formatWeatherDescription(self, data):
        return data["weather"][0]["description"].capitalize()

    def _showWeather(self, cityId):
        # Get and cache the data if not in cache
        if not cityId in self.cachedCities or self.cachedCities[cityId]["time"] < time.time() - 600:
            try:
                httpResponse = urlopen("{}/weather?id={}&appid={}".format(self.baseUrl, cityId, self.key))
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

            cache = {'time': time.time(), 'data': data}
            self.cachedCities[cityId] = cache

        # Retrieve from cache
        data = self.cachedCities[cityId]["data"]

        # Format and show
        formattedData = [self._formatTemperature(data),
                         self._formatWeatherDescription(data)]

        self.q.put([Action.setHeader, self._formatPlaceName(data)])
        self.q.put([Action.replaceCommandList, []])
        self.q.put([Action.replaceEntryList, formattedData])

    def _showForecast(self, cityId, timestamp):
        for forecastEntry in self.cachedForecasts[cityId]["data"]["list"]:
            if forecastEntry["dt"] == timestamp:
                cityData = self.cachedForecasts[cityId]["data"]["city"]
                formattedData = [self._formatTemperature(forecastEntry),
                                 self._formatWeatherDescription(forecastEntry)]

                self.q.put([Action.setHeader, "{} ({})".format(cityData["name"], cityData["country"])])
                self.q.put([Action.replaceEntryList, formattedData])

    def _retrieveForecast(self, cityId):
        if not cityId in self.cachedForecasts or self.cachedForecasts[cityId]["time"] < time.time() - 600:
            try:
                httpResponse = urlopen("{}/forecast?id={}&appid={}".format(self.baseUrl, cityId, self.key))
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

            cache = {'time': time.time(), 'data': data}
            self.cachedForecasts[cityId] = cache

        cityData = self.cachedForecasts[cityId]["data"]["city"]

        self.q.put([Action.setHeader, "{} ({})".format(cityData["name"], cityData["country"])])
        self.q.put([Action.replaceCommandList, []])
        self.q.put([Action.replaceEntryList, []])

        for forecastEntry in self.cachedForecasts[cityId]["data"]["list"]:
            self.q.put([Action.addEntry, datetime.fromtimestamp(forecastEntry["dt"])])

    def stop(self):
        pass

    def selectionMade(self, selection):
        if len(selection) == 0:
            self._setMainCommands()
            self.q.put([Action.replaceEntryList, list(self.entries.keys())])
        elif len(selection) == 1:
            parts = selection[0]["value"].split(" ")
            if selection[0]['type'] == SelectionType.entry:
                # Entry selected, act is if we called the weather function to
                # reduce code repetition
                self.q.put([Action.setSelection, [{'type': SelectionType.command, 'value': 'weather {}'.format(" ".join(parts))}]])
                return

            cityId = self._getCityId(" ".join(parts[1:]))

            # Remove commands
            self.q.put([Action.replaceCommandList, []])

            if parts[0] == "forecast":
                self._retrieveForecast(cityId)
            elif parts[0] == "weather":
                self._showWeather(cityId)
            else:
                self.q.put([Action.criticalError, "Unexpected selectionMade value: {}".format(selection)])
        elif len(selection) == 2:
            if selection[0]["type"] != SelectionType.command:
                self.q.put([Action.criticalError, "Unexpected selectionMade value: {}".format(selection)])

            parts = selection[0]["value"].split(" ")
            if parts[0] == "forecast":
                try:
                    timestamp = selection[1]["value"].timestamp()
                except AttributeError:
                    # The user selected the city name
                    self.q.put([Action.setSelection, selection[:-1]])
                    return

                self._showForecast(self._getCityId(" ".join(parts[1:])), timestamp)
            elif parts[0] == "weather":
                self.q.put([Action.copyToClipboard, selection[1]["value"]])
                self.q.put([Action.close])
            else:
                self.q.put([Action.criticalError, "Unexpected selectionMade value: {}".format(selection)])
        elif len(selection) == 3:
            # We can only get this deep if we use forecast, just copy the entry to the clipboard and close
            self.q.put([Action.copyToClipboard, selection[2]["value"]])
            self.q.put([Action.close])
        else:
            self.q.put([Action.criticalError, "Unexpected selectionMade value: {}".format(selection)])

    def processResponse(self, response):
        pass
