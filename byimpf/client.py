import datetime
import logging
import threading
import time
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Dict, Optional, Union
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import requests
import schedule
from bs4 import BeautifulSoup
from requests import HTTPError, Response


def url_with_params(url: str, query_params: Dict[str, str]) -> str:
    scheme, netloc, path, _, fragment = urlsplit(url)
    query_string = urlencode(query_params, doseq=True)
    return urlunsplit((scheme, netloc, path, query_string, fragment))


class Variant(Enum):
    OMICRON_BA_1 = "OMC_BA1"
    OMICRON_BA_4_5 = "OMC_BA4-5"


class VaccinationType(Enum):
    FIRST = "FIRST"
    SECOND = "SECOND"
    BOOST = "BOOST"


class Vaccine(Enum):
    ASTRA_ZENECA = "001"
    BIONTECH_PFIZER = "002"
    MODERNA = "003"
    JANSSEN = "005"
    NUVAXOVID = "006"
    VALNEVA = "008"
    BIONTECH_PFIZER_BA1 = "009"
    MODERNA_SPIKEVAX_0 = "010"
    BIONTECH_PFIZER_BA45 = "011"

    @staticmethod
    def from_id(vaccine_id: str) -> "Vaccine":
        for v in Vaccine:
            if v.value == vaccine_id:
                return v

        raise ValueError("Unknown vaccine ID")


@dataclass
class AppointmentOptions:
    earliest_day: date
    latest_day: date
    book: bool
    variant: Variant
    first_vaccine: Vaccine
    vaccination_type: VaccinationType

    def __repr__(self) -> str:
        return "\n".join(
            [
                f"First possible date: {self.earliest_day or 'earliest available'}",
                f"Last possible date: {self.latest_day or 'no limit'}",
                f"Vaccination type: {self.vaccination_type.value}",
                f"First vaccination: {self.first_vaccine.value if self.first_vaccine else '?'}",
                f"Variant: {self.variant or 'any'}",
                f"{'Will' if self.book else 'Will not'} attempt to book",
            ]
        )


class ImpfChecker:
    MAIN_PAGE = "https://impfzentren.bayern/citizen/"
    LOGIN_URL = "https://ciam.impfzentren.bayern/auth/realms/C19V-Citizen/protocol/openid-connect/auth"
    TOKEN_URL = "https://ciam.impfzentren.bayern/auth/realms/C19V-Citizen/protocol/openid-connect/token"
    APPOINTMENTS_URL_FORMAT = (
        "https://impfzentren.bayern/api/v1/citizens/{}/appointments"
    )
    NTFY_SH_URL = "https://ntfy.sh/"

    def auth_token(self):
        if self._auth_token is None:
            try:
                self._login()
            except HTTPError:
                logging.error("Login failed.")
                exit(1)
        return self._auth_token

    def __init__(
        self,
        username: str,
        password: str,
        citizen_id: str,
        ntfy_topic: Optional[str] = None,
    ):
        self._user = username
        self._password = password
        self.citizen_id = citizen_id
        self.session = requests.Session()
        self._ntfy_topic = ntfy_topic
        self._auth_token: Optional[str] = None
        self._auth_token_expiry: Optional[datetime.datetime] = None
        self._refresh_token: Optional[str] = None

    def __enter__(self):
        self.stop_schedule = self.run_schedule()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_schedule.set()

    @staticmethod
    def run_schedule(interval=1):
        cease_continuous_run = threading.Event()

        class ScheduleThread(threading.Thread):
            @classmethod
            def run(cls):
                while not cease_continuous_run.is_set():
                    schedule.run_pending()
                    time.sleep(interval)

        continuous_thread = ScheduleThread()
        continuous_thread.start()
        return cease_continuous_run

    def reset_session(self):
        logging.debug("Resetting the session")

        self.session = requests.Session()
        self._auth_token = None
        self._refresh_token = None

    def _submit_form(
        self, url: str, body: Dict[str, str], allow_redirects: bool = True
    ) -> Response:
        """
        Submits a form to the API

        :param url: The endpoint to post the form to
        :param body: The form fields and their values
        :param allow_redirects: Whether to follow redirects returned by the API

        :return: The full Response object
        """

        return self.session.post(
            url,
            headers=self._headers(
                **{"Content-Type": "application/x-www-form-urlencoded"}
            ),
            data=body,
            allow_redirects=allow_redirects,
        )

    def _headers(self, with_auth: bool = False, **additional_headers):
        """
        :param with_auth: Whether to include the Authorization header
        :param additional_headers: A mapping of additional headers to add

        :return: a dictionary of headers required to make calls to the API
        """

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:95.0) Gecko/20100101 Firefox/95.0",
            "Accept": "*/*",
        }

        if with_auth:
            headers["Authorization"] = f"Bearer {self.auth_token()}"

        headers.update(**additional_headers)
        return headers

    @property
    def _login_url(self) -> str:
        query_params = dict(
            client_id="c19v-frontend",
            redirect_uri=self.MAIN_PAGE,
            state=uuid4(),
            response_mode="fragment",
            response_type="code",
            scope="openid",
            nonce=uuid4(),
            ui_locales="de",
        )
        return url_with_params(self.LOGIN_URL, query_params)

    def _get_login_action(self) -> str:
        """
        :return: The URL of the endpoint to which the login form posts
        """
        login_form_rsp = self.session.get(self._login_url, headers=self._headers())
        login_form_rsp.raise_for_status()
        return BeautifulSoup(login_form_rsp.text, "html.parser").find(
            id="kc-form-login"
        )["action"]

    def _login(self):
        """
        Attempts to log the user in

        :raise HTTPError if unsuccessful
        """
        logging.debug("Logging in")

        login_resp = self._submit_form(
            self._get_login_action(),
            {"username": self._user, "password": self._password, "credentialId": ""},
            allow_redirects=False,
        )

        login_resp.raise_for_status()

        _, state = login_resp.headers.get("Location").split("#", maxsplit=1)
        code = parse_qs(state)["code"][0]
        self.refresh_auth_token(code)

        # Check every 10 seconds if we need to refresh the auth token
        schedule.every(10).seconds.do(self.refresh_auth_token)

    @property
    def is_auth_token_expired(self) -> bool:
        return (
            self._auth_token_expiry
            and self._auth_token_expiry - datetime.datetime.now()
            < datetime.timedelta(seconds=30)
        )

    def refresh_auth_token(self, code: Optional[str] = None):
        """
        Authentication tokens are required for calls to the API. They are only valid for a limited time, but can be
        refreshed. This method fetches the latest authentication token if necessary.

        Optionally accepts an authorisation code obtained from the login endpoint. If an authentication code is passed,
        this method fetches the matching token.

        :param code: Authorisation code retrieved from the login endpoint
        """
        if not code and not self.is_auth_token_expired:
            return

        if code:
            logging.debug("Getting auth token from auth code")
            token_rsp = self._submit_form(
                self.TOKEN_URL,
                {
                    "code": code,
                    "grant_type": "authorization_code",
                    "client_id": "c19v-frontend",
                    "redirect_uri": "https://impfzentren.bayern/citizen/",
                },
            )
        else:
            logging.debug("Refreshing auth token")
            token_rsp = self._submit_form(
                self.TOKEN_URL,
                {
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                    "client_id": "c19v-frontend",
                },
            )
        token_rsp.raise_for_status()
        rsp_json = token_rsp.json()

        self._auth_token, self._auth_token_expiry, self._refresh_token = (
            rsp_json["access_token"],
            datetime.datetime.now()
            + datetime.timedelta(seconds=rsp_json["expires_in"]),
            rsp_json["refresh_token"],
        )

    def _appointments_url(self, resource: Optional[str] = None):
        return self.APPOINTMENTS_URL_FORMAT.format(self.citizen_id) + (
            resource if resource is not None else ""
        )

    def _find_appointment(
        self,
        options: AppointmentOptions,
    ) -> Optional[Dict]:
        """
        Finds an appointment in the user's vaccination centre

        :param options: The options for the appointment

        :return: The JSON payload if an appointment was found, otherwise None
        """

        params = {
            "timeOfDay": "ALL_DAY",
            "lastDate": options.earliest_day,
            "lastTime": "00:00",
            "vaccinationType": options.vaccination_type.value,
        }

        if options.variant is not None:
            params["variant"] = options.variant.value

        if options.first_vaccine is not None:
            params["firstVaccinationVaccine"] = options.first_vaccine.value

        appt_rsp = self.session.get(
            url_with_params(
                self._appointments_url("/next"),
                params,
            ),
            headers=self._headers(with_auth=True),
        )

        if appt_rsp.status_code == 404:
            return None

        if appt_rsp.status_code // 100 != 2:
            logging.debug("Unexpected status code %d", appt_rsp.status_code)

        if appt_rsp.status_code == 401:
            self.reset_session()
            return None

        appt = appt_rsp.json()

        if (
            options.latest_day
            and datetime.date.fromisoformat(appt["vaccinationDate"])
            > options.latest_day
        ):
            # We found an appointment, but it's too far in the future
            return None

        return appt

    def find(
        self,
        options: AppointmentOptions,
    ) -> bool:
        """
        Finds an appointment in the user's vaccination centre

        :param options: The options for the appointment

        :return:        False if no appointment found or booking failed. True otherwise.
        """
        if options.earliest_day is None:
            options.earliest_day = date.today()

        appt = self._find_appointment(options)
        if appt is None:
            logging.info("No appointment available")
            return False

        logging.info(
            "Found appointment on %s at %s",
            appt["vaccinationDate"],
            appt["vaccinationTime"],
        )

        if options.book:
            return self._book(appt)
        else:
            self.notify(
                f"An appointment is available on {appt['vaccinationDate']} at {appt['vaccinationTime']}."
            )

        return True

    def _book(self, payload: Dict[str, Union[str, Dict[str, bool]]]) -> bool:
        """
        Books an appointment

        :param payload: The appointment payload as returned by the _find() method
        :return: True if the booking was successful, False otherwise
        """

        payload["reminderChannel"] = {"reminderByEmail": True, "reminderBySms": True}

        book_rsp = self.session.post(
            self._appointments_url(),
            json=payload,
            headers=self._headers(with_auth=True),
        )

        if book_rsp.status_code != 200:
            logging.error("Error booking appointment. Status %s", book_rsp.status_code)
            return False

        logging.info("Appointment booked.")

        self.notify(
            (
                f"Appointment booked for {payload['vaccinationDate']} at {payload['vaccinationTime']}."
                "Please check your e-mails."
            )
        )

        return True

    def print_appointments(self):
        """
        Prints the upcoming appointments
        """

        appts_rsp = self.session.get(
            self._appointments_url(), headers=self._headers(with_auth=True)
        )

        if appts_rsp.status_code != 200:
            logging.error("Error retrieving appointments")
            return

        appts = appts_rsp.json().get("futureAppointments")

        if not appts:
            logging.info("No appointments found")
            return

        for appt in appts:
            address = appt["site"]["address"]

            logging.info(
                "Upcoming appointment at %s (%s) on %s at %s",
                appt["site"]["name"],
                "{} {}, {} {}".format(
                    address["street"],
                    address["streetNumber"],
                    address["zip"],
                    address["city"],
                ),
                appt["slotId"]["date"],
                appt["slotId"]["time"],
            )

    def notify(self, title: str):
        if not self._ntfy_topic:
            return

        requests.post(
            self.NTFY_SH_URL,
            json={
                "topic": self._ntfy_topic,
                "message": title,
                "title": "",
                "tags": ["syringe"],
                "priority": 4,
                "actions": [
                    {
                        "action": "view",
                        "label": "BayIMCO portal",
                        "url": f"https://impfzentren.bayern/citizen/overview/{self.citizen_id}",
                        "clear": True,
                    }
                ],
            },
        )
