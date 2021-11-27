import argparse
import datetime
import json
import logging
import threading
import time
from datetime import date
from typing import Dict, Optional, Union
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import requests
import schedule
from bs4 import BeautifulSoup
from requests import HTTPError, Response
from tenacity import Retrying, wait_fixed

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def url_with_params(url: str, query_params: Dict[str, str]) -> str:
    scheme, netloc, path, _, fragment = urlsplit(url)
    query_string = urlencode(query_params, doseq=True)
    return urlunsplit((scheme, netloc, path, query_string, fragment))


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


class ImpfChecker:
    MAIN_PAGE = "https://impfzentren.bayern/citizen/"
    LOGIN_URL = "https://ciam.impfzentren.bayern/auth/realms/C19V-Citizen/protocol/openid-connect/auth"
    TOKEN_URL = "https://ciam.impfzentren.bayern/auth/realms/C19V-Citizen/protocol/openid-connect/token"
    APPOINTMENTS_URL_FORMAT = (
        "https://impfzentren.bayern/api/v1/citizens/{}/appointments"
    )

    def auth_token(self):
        if self._auth_token is None:
            try:
                self._login()
            except HTTPError:
                logging.error("Login failed.")
                exit(1)
        return self._auth_token

    def __init__(self, username: str, password: str, citizen_id: str):
        self._user = username
        self._password = password
        self.citizen_id = citizen_id
        self.session = requests.Session()
        self._auth_token = None
        self._refresh_token = None

    def __enter__(self):
        self.stop_schedule = run_schedule()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_schedule.set()

    def reset_session(self):
        logging.debug("Resetting the session")

        self.session = requests.Session()
        self._auth_token = None
        self._refresh_token = None

    def _submit_form(
        self,
        url: str,
        body: Dict[str, str],
        allow_redirects: bool = True,
    ) -> Response:
        """
        Submits a form to the API

        :param url: The endpoint to post the form to
        :param body: The form fields and their values
        :param allow_redirects: Whether or not to follow redirects returned by the API

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
        :param with_auth: Whether or not to include the Authorization header
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
            {
                "username": self._user,
                "password": self._password,
                "credentialId": "",
            },
            allow_redirects=False,
        )

        login_resp.raise_for_status()

        _, state = login_resp.headers.get("Location").split("#", maxsplit=1)
        code = parse_qs(state)["code"][0]
        self.refresh_auth_token(code)

        # Auth tokens are valid for 300 seconds, so let's refresh ours after 270.
        schedule.every(270).seconds.do(self.refresh_auth_token)

    def refresh_auth_token(self, code: Optional[str] = None):
        logging.debug("Refreshing auth token")

        if code:
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

        self._auth_token, self._refresh_token = (
            rsp_json["access_token"],
            rsp_json["refresh_token"],
        )

    def _appointments_url(self, resource: Optional[str] = None):
        return self.APPOINTMENTS_URL_FORMAT.format(self.citizen_id) + (
            resource if resource is not None else ""
        )

    def _find_appointment(self, earliest_day) -> Optional[Dict]:
        """
        Finds an appointment in the user's vaccination centre

        :param earliest_day:    The earliest acceptable day in ISO format (YYYY-MM-DD)

        :return: The JSON payload if an appointment was found, otherwise None
        """
        appt_rsp = self.session.get(
            url_with_params(
                self._appointments_url("/next"),
                {
                    "timeOfDay": "ALL_DAY",
                    "lastDate": earliest_day,
                    "lastTime": "00:00",
                },
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

        return appt_rsp.json()

    def find(self, earliest_day: Optional[str] = None, *, book: bool = False) -> bool:
        """
        Finds an appointment in the user's vaccination centre

        :param earliest_day:    The earliest acceptable day in ISO format (YYYY-MM-DD)
        :param book:            Whether or not to book the appointment

        :return:    False if no appointment found or booking failed.
                    True if the booking was successful or an appointment was found and no booking requested.
        """
        if earliest_day is None:
            earliest_day = date.today()

        appt = self._find_appointment(earliest_day.isoformat())
        if appt is None:
            logging.info("No appointment available")
            return False

        logging.info("Found appointment: %s", json.dumps(appt))

        if book:
            return self._book(appt)

        return True

    def _book(self, payload: Dict[str, Union[str, Dict[str, bool]]]) -> bool:
        """
        Books an appointment

        :param payload: The appointment payload as returned by the _find() method
        :return: True if the booking was successful, False otherwise
        """

        payload["reminderChannel"] = {
            "reminderByEmail": True,
            "reminderBySms": True,
        }

        book_rsp = self.session.post(
            self._appointments_url(),
            json=payload,
            headers=self._headers(with_auth=True),
        )

        if book_rsp.status_code != 200:
            logging.error(f"Error booking appointment. Status %d", book_rsp.status_code)
            return False

        logging.info("Appointment booked.")
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


def main():
    parser = argparse.ArgumentParser(
        description="Appointment checker and booker for Bavarian vaccination centres"
    )
    parser.add_argument(
        "--citizen-id",
        type=str,
        required=True,
        help=(
            "Your citizen ID. "
            "Find it in the address bar of your browser after selecting the person in the web portal."
        ),
    )
    parser.add_argument(
        "--email", type=str, required=True, help="Your login email address"
    )
    parser.add_argument(
        "--password", type=str, required=True, help="Your login password"
    )
    parser.add_argument(
        "--earliest-day",
        type=datetime.date.fromisoformat,
        help="The earliest day from which to find an appointment, in ISO format (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="The interval in seconds between checks. If not passed, only one check is made.",
    )
    parser.add_argument(
        "--book",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Whether to book the appointment if found",
    )
    args = parser.parse_args()

    checker = ImpfChecker(
        username=args.email,
        password=args.password,
        citizen_id=args.citizen_id,
    )

    if args.interval is not None:
        with checker:
            for i, attempt in enumerate(
                Retrying(wait=wait_fixed(args.interval)), start=1
            ):
                with attempt:
                    logging.debug("Trying to find appointment (attempt %d)", i)
                    if not checker.find(earliest_day=args.earliest_day, book=args.book):
                        raise Exception("Unsuccessful attempt")
    else:
        checker.find(earliest_day=args.earliest_day, book=args.book)

    if args.book:
        checker.print_appointments()


if __name__ == "__main__":
    main()
