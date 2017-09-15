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
        self.settings = settings

        self.entries = {}
        self.context_entries = {}
        self.cachedCities = {}
        self.cachedForecasts = {}

        self.scriptLocation = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        
        self._get_entries()
        self._set_main_commands()

    def _get_entries(self):
        with open(os.path.join(self.scriptLocation, 'city.list.json')) as f:
            for line in f:
                city = json.loads(line)
                formattedCity = "{} ({})".format(city['name'], city['country'])
                self.entries[formattedCity] = city
                self.context_entries[formattedCity] = ["Current weather", "Forecast"]

        self._set_entries()

    def _set_entries(self):
        # While this goes against Pext's module development recommendation to
        # at least show some entries as soon as possible, appending a list of
        # this size using Action.add_entry one-by-one is simply too slow
        self.q.put([Action.replace_entry_list, sorted(list(self.entries.keys()))])
        if self.settings['_api_version'] >= [0, 5, 0]:
            self.q.put([Action.replace_entry_context_dict, self.context_entries])

    def _set_main_commands(self):
        self.q.put([Action.set_header])
        if self.settings['_api_version'] < [0, 5, 0]:
            self.q.put([Action.replace_command_list, ["weather <full city name>",
                                                      "forecast <full city name>"]])

    def _get_city_id(self, identifier):
        return self.entries[identifier]['_id']

    def _format_data(self, data):
        return [
                   self._format_place_name(data),
                   self._format_temperature(data),
                   self._format_weather_description(data)
               ]

    def _format_place_name(self, data):
        return "{} ({})".format(data['name'], data["sys"]["country"])

    def _format_temperature(self, data):
        kelvin = data["main"]["temp"]
        celcius = kelvin - 273.15
        fahrenheit = kelvin * 9 / 5 - 459.67
        return "{:.2f} °C / {:.2f} °F".format(celcius, fahrenheit)

    def _format_weather_description(self, data):
        return data["weather"][0]["description"].capitalize()

    def _show_weather(self, cityId):
        # Get and cache the data if not in cache
        if not cityId in self.cachedCities or self.cachedCities[cityId]["time"] < time.time() - 600:
            try:
                httpResponse = urlopen("{}/weather?id={}&appid={}".format(self.baseUrl, cityId, self.key))
            except URLError as e:
                self.q.put([Action.add_error, "Failed to request weather data: {}".format(e)])
                self.q.put([Action.set_selection, []])
                return

            responseData = httpResponse.read().decode("utf-8")
            try:
                data = json.loads(responseData)
            except json.JSONDecodeError as e:
                self.q.put([Action.add_error, "Failed to decode weather data: {}".format(e)])
                self.q.put([Action.set_selection, []])
                return

            if data['cod'] != 200:
                self.q.put([Action.add_error, "Failed to retrieve weather data: {} ({})".format(data['message'], data['cod'])])
                self.q.put([Action.set_selection, []])
                return

            cache = {'time': time.time(), 'data': data}
            self.cachedCities[cityId] = cache

        # Retrieve from cache
        data = self.cachedCities[cityId]["data"]

        # Format and show
        formattedData = [self._format_temperature(data),
                         self._format_weather_description(data)]

        self.q.put([Action.set_header, self._format_place_name(data)])
        self.q.put([Action.replace_command_list, []])
        self.q.put([Action.replace_entry_list, formattedData])

    def _show_forecast(self, cityId, timestamp):
        for forecastEntry in self.cachedForecasts[cityId]["data"]["list"]:
            if forecastEntry["dt"] == timestamp:
                cityData = self.cachedForecasts[cityId]["data"]["city"]
                formattedData = [self._format_temperature(forecastEntry),
                                 self._format_weather_description(forecastEntry)]

                self.q.put([Action.set_header, "{} ({})".format(cityData["name"], cityData["country"])])
                self.q.put([Action.replace_entry_list, formattedData])

    def _retrieve_forecast(self, cityId):
        if not cityId in self.cachedForecasts or self.cachedForecasts[cityId]["time"] < time.time() - 600:
            try:
                httpResponse = urlopen("{}/forecast?id={}&appid={}".format(self.baseUrl, cityId, self.key))
            except URLError as e:
                self.q.put([Action.add_error, "Failed to request weather data: {}".format(e)])
                self.q.put([Action.set_selection, []])
                return

            responseData = httpResponse.read().decode("utf-8") 
            try:
                data = json.loads(responseData)
            except json.JSONDecodeError as e:
                self.q.put([Action.add_error, "Failed to decode weather data: {}".format(e)])
                self.q.put([Action.set_selection, []])
                return

            cache = {'time': time.time(), 'data': data}
            self.cachedForecasts[cityId] = cache

        cityData = self.cachedForecasts[cityId]["data"]["city"]

        self.q.put([Action.set_header, "{} ({})".format(cityData["name"], cityData["country"])])
        self.q.put([Action.replace_command_list, []])
        self.q.put([Action.replace_entry_list, []])

        for forecastEntry in self.cachedForecasts[cityId]["data"]["list"]:
            self.q.put([Action.add_entry, datetime.fromtimestamp(forecastEntry["dt"])])

    def stop(self):
        pass

    def selection_made(self, selection):
        if len(selection) == 0:
            self._set_entries()
            self._set_main_commands()
        elif len(selection) == 1:
            parts = selection[0]["value"].split(" ")
            if selection[0]['type'] == SelectionType.entry:
                # Entry selected, act is if we called the weather/forecast function to
                # reduce code repetition
                if self.settings['_api_version'] >= [0, 4, 0]:
                    if selection[0]['context_option'] == "Forecast":
                        self.q.put([Action.set_selection, [{'type': SelectionType.command, 'value': 'forecast {}'.format(" ".join(parts))}]])
                        return

                self.q.put([Action.set_selection, [{'type': SelectionType.command, 'value': 'weather {}'.format(" ".join(parts))}]])
                return

            cityId = self._get_city_id(" ".join(parts[1:]))

            # Remove commands
            self.q.put([Action.replace_command_list, []])

            if parts[0] == "forecast":
                self._retrieve_forecast(cityId)
            elif parts[0] == "weather":
                self._show_weather(cityId)
            else:
                self.q.put([Action.critical_error, "Unexpected selection_made value: {}".format(selection)])
        elif len(selection) == 2:
            if selection[0]["type"] != SelectionType.command:
                self.q.put([Action.critical_error, "Unexpected selection_made value: {}".format(selection)])

            parts = selection[0]["value"].split(" ")
            if parts[0] == "forecast":
                try:
                    timestamp = selection[1]["value"].timestamp()
                except AttributeError:
                    # The user selected the city name
                    self.q.put([Action.set_selection, selection[:-1]])
                    return

                self._show_forecast(self._get_city_id(" ".join(parts[1:])), timestamp)
            elif parts[0] == "weather":
                self.q.put([Action.copy_to_clipboard, selection[1]["value"]])
                self.q.put([Action.close])
            else:
                self.q.put([Action.critical_error, "Unexpected selection_made value: {}".format(selection)])
        elif len(selection) == 3:
            # We can only get this deep if we use forecast, just copy the entry to the clipboard and close
            self.q.put([Action.copy_to_clipboard, selection[2]["value"]])
            self.q.put([Action.close])
        else:
            self.q.put([Action.critical_error, "Unexpected selection_made value: {}".format(selection)])

    def process_response(self, response):
        pass
