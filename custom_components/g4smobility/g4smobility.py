import re
import time
import json
import requests
from datetime import datetime, timedelta, timezone, UTC

from bs4 import BeautifulSoup


class G4SMobility():
    """docstring for G4SMobility"""

    def __init__(self, username, password):
        self.endpoint = "https://g4smobility.com"
        self.username = username
        self.password = password
        self.options = {}
        self.units = {}
        self.session = requests.Session()
        self.user_authentication()

    def parse_options(self, options):
        self.options["user"] = options["Id"]
        for option in options["Preferences"]:
            if option["Value"] in ["Km/h", "Miles/h", "Knots"]:
                self.options["speed_sign"] = option["Value"]
            elif option["Value"] in ["celsius", "fahrenheit"]:
                self.options["temp_sign"] = option["Text"]
            elif match := re.match(r"\(GMT ([-+]*\d+):(\d+)", option["Text"]):
                tz_offset = int(match.group(1)) * 60 - int(match.group(2))
                tz = timezone(timedelta(minutes=tz_offset))
                self.options["timezone"] = tz
            elif "dateformat." in option["Text"]:
                 dateformat = f"{option["Value"]} %H:%M:%S"
                 dateformat = dateformat.replace("dd", "%d")
                 dateformat = dateformat.replace("MMM", "%b")
                 dateformat = dateformat.replace("mm", "%m")
                 dateformat = dateformat.replace("yyyy", "%Y")
                 self.options["dateformat"] = dateformat


    def user_authentication(self):
        req = self.session.post(
            f"{self.endpoint}/Account/LogOnV3",
            data={
                "username": self.username,
                "password": self.password,
                "action": "log on",
                "ReturnUrl": "/User/Fetch",
            },
        )
        try:
            options = req.json()
            self.parse_options(options)
            # self.session.get(f"{self.endpoint}/Live/Unit/Filter?FilterByText=")
            return True
        except Exception as err:
            print(req.status_code, err)
        return False

    def test_urls(self):
        req = self.session.get(f"{self.endpoint}/Live/Unit/List").text
        req2 = self.session.get(f"{self.endpoint}/Live/Unit/Units").text
        print(len(req), len(req2))

    def get_units(self, remember=True):
        units = {}
        try:
            req = self.session.get(f"{self.endpoint}/Live/Unit/Units?ResetRequestDate=true").json()
        except:
            self.user_authentication()
            req = self.session.get(f"{self.endpoint}/Live/Unit/Units?ResetRequestDate=true").json()

        for unit in req["Units"]:
            if unit["HasData"]:
                soup = BeautifulSoup(unit["HtmlControl"], "html.parser")
                curraux = soup.select_one(".curraux-details")
                binary_sensors = {}
                if curraux is not None:
                    for num, li in enumerate(curraux.find_all("li")):
                        classes = li.find("div")["class"]
                        if len(classes) == 5:
                            icon = classes[1].replace("t-io-", "")
                            color = classes[2].replace("i-c-", "")
                            title = li["title"].split(" <br> ")[0].lower()
                            title = title.removesuffix(" error")
                            title = title.removesuffix(" off")
                            title = title.removesuffix(" on")
                            title = title.removesuffix(" ok")
                            title = title.removesuffix(" active")
                            title = title.removesuffix(" inactive")
                            title = title.removesuffix(" inserted")
                            title = title.removesuffix(" pulled")
                            title = title.removesuffix(" pull out")
                            title = title.removesuffix(" unlocked")
                            title = title.removesuffix(" locked")
                            title = title.removesuffix(" closed")
                            title = title.removesuffix(" open")
                            title = title.removesuffix("ς")
                            title = title.removeprefix("κλείσιμο ")
                            title = title.removeprefix("άνοιγμα ")
                            title = title.removeprefix("no-")
                            if title == "unlock":
                                title = "lock"
                            if title == "authorized":
                                title = "unauthorized"
                            active = None
                            if color in ["green", "blue", "brightgreen", "offwhite"]:
                                active = False
                            elif color in ["yellow", "red", "grey", "lightgrey"]:
                                active = True
                            binary_sensors[f"{title}_{num}"] = {
                                "active": active,
                                "title": title,
                                "num": num,
                            }
                            # print(active, "\t\t\t", li.find("div")["unitname"], " \t\t\t\t\t\t", title)
                updated_str = unit["Unit"]["LatestPointReceivedDateTimeFormatted"]
                updated_obj = datetime.strptime(updated_str, self.options["dateformat"])
                updated_tz = updated_obj.replace(tzinfo=self.options["timezone"]).astimezone()
                updated_before = (datetime.now().astimezone() - updated_tz).total_seconds()
                available = False
                if updated_before < 60 * 60 * 13:
                    available = True

                sensors = {
                    "Odometer": {
                        "value": int(unit["Unit"]["OdometerFormatted"].split()[0]),
                        "sign": unit["Unit"]["OdometerFormatted"].split()[1],
                    },
                    "Speed": {
                        "value": unit["Unit"]["Speed"],
                        "sign": self.options["speed_sign"],
                    },
                    "Heading": {
                        "value": unit["Unit"]["Heading"],
                        "sign": "°",
                    },
                    "State": {
                        "value": unit["Unit"]["StatusFixed"],
                        "sign": None,
                    },
                    "Last sent": {
                        "value": updated_tz,
                        "sign": None,
                        "type": "diagnostic",
                    }
                }
                for sensor in unit["Unit"]["SensorInputs"]:
                    if sensor["MeasurementSign"] == "°":
                        sensor["MeasurementSign"] = self.options["temp_sign"]
                    sensor_type = None
                    if sensor["Description"] in ["Signal Strength", "Satellite Count", "Internal Battery", "External Battery"]:
                        sensor_type = "diagnostic"

                    sensors[sensor["Description"]] = {
                        "value": float(sensor["Value"]),
                        "sign": sensor["MeasurementSign"],
                        "type": sensor_type,
                    }

                units[unit["Unit"]["UnitId"]] = {
                    "available": available,
                    "id": unit["Unit"]["UnitId"],
                    "name": unit["Unit"]["Name"],
                    "lat": unit["Unit"]["Latitude"],
                    "lon": unit["Unit"]["Longitude"],
                    "sensors": sensors,
                    "binary_sensors": binary_sensors,
                }

        if remember:
            offline_unitids = set(self.units.keys()) - set(units.keys())
            self.units.update(units)
            for unitid in offline_unitids:
                self.units[unitid]["available"] = False
        else:
            self.units = units

        return self.units

    def update(self):
        self.get_units()
