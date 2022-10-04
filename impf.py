import argparse
import datetime
import logging

from tenacity import Retrying, wait_fixed

from byimpf.client import (
    AppointmentOptions,
    ImpfChecker,
    VaccinationType,
    Vaccine,
    Variant,
)


def parse_variant(variant: str) -> Variant:
    variant = variant.lower()

    if variant == "ba1":
        return Variant.OMICRON_BA_1

    if variant == "ba45":
        return Variant.OMICRON_BA_4_5

    raise ValueError(f"Unknown variant '{variant}'. If passed, must be either ba1 or ba45")


def parse_dose(dose: str) -> VaccinationType:
    dose = dose.lower()

    if dose in ("first", "1"):
        return VaccinationType.FIRST

    if dose in ("second", "2"):
        return VaccinationType.SECOND

    if dose in ("boost", "booster", "3", "4"):
        return VaccinationType.BOOST

    raise ValueError("Must be either first, second, or boost")


def main():
    parser = argparse.ArgumentParser(description="Appointment checker and booker for Bavarian vaccination centres")
    parser.add_argument(
        "--citizen-id",
        type=str,
        required=True,
        help=(
            "Your citizen ID. "
            "Find it in the address bar of your browser after selecting the person in the web portal."
        ),
    )
    parser.add_argument("--email", type=str, required=True, help="Your login email address")
    parser.add_argument("--password", type=str, required=True, help="Your login password")
    parser.add_argument(
        "--earliest-day",
        type=datetime.date.fromisoformat,
        help="The earliest day from which to find an appointment, in ISO format (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--latest-day",
        type=datetime.date.fromisoformat,
        help="The latest acceptable day for an appointment, in ISO format (YYYY-MM-DD)",
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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Whether to print debug log output",
    )
    parser.add_argument(
        "--dose",
        type=parse_dose,
        default=VaccinationType.BOOST,
        required=False,
        help="Which vaccination to looking for: first, second or boost. Defaults to boost.",
    )
    parser.add_argument(
        "--first-vaccine-id",
        type=Vaccine.from_id,
        required=False,
        help="The ID of the vaccine that was used for the first jab. Only required for the second vaccination.",
        dest="first_vaccine",
    )
    parser.add_argument(
        "--variant",
        type=parse_variant,
        default=None,
        required=False,
        help="Variants to find vaccines for; either ba1 or ba45. Leave blank for any.",
    )
    parser.add_argument(
        "--ntfy-topic",
        type=str,
        default=None,
        required=False,
        help="ntfy.sh topic to send a message to on success. See https://ntfy.sh for details.",
    )
    args = parser.parse_args()

    if args.dose == VaccinationType.SECOND and args.first_vaccine is None:
        raise ValueError("The ID of the first vaccine must be passed if we're looking for a second dose.")

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG if args.debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    checker = ImpfChecker(
        username=args.email,
        password=args.password,
        citizen_id=args.citizen_id,
        ntfy_topic=args.ntfy_topic,
    )

    appt_options = AppointmentOptions(
        earliest_day=args.earliest_day,
        latest_day=args.latest_day,
        book=args.book,
        vaccination_type=args.dose,
        first_vaccine=args.first_vaccine,
        variant=args.variant,
    )

    startup_message = "\n".join(
        [
            "Finding an appointment with the following options:",
            f"E-mail: {args.email}",
            f"Citizen ID: {args.citizen_id}",
            f"Notification topic: {args.ntfy_topic}",
            f"Dose: {args.dose.value}",
            f"{appt_options}",
        ]
    )

    logging.info(startup_message)

    if args.interval is not None:
        with checker:
            for i, attempt in enumerate(Retrying(wait=wait_fixed(args.interval)), start=1):
                with attempt:
                    logging.debug("Trying to find appointment (attempt %d)", i)
                    if not checker.find(appt_options):
                        raise Exception("Unsuccessful attempt")
    else:
        checker.find(appt_options)

    if args.book:
        checker.print_appointments()


if __name__ == "__main__":
    main()
