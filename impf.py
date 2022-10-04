import argparse
import datetime
import logging

from tenacity import Retrying, wait_fixed

from byimpf.client import ImpfChecker


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
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG if args.debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    checker = ImpfChecker(
        username=args.email, password=args.password, citizen_id=args.citizen_id
    )

    if args.interval is not None:
        with checker:
            for i, attempt in enumerate(
                Retrying(wait=wait_fixed(args.interval)), start=1
            ):
                with attempt:
                    logging.debug("Trying to find appointment (attempt %d)", i)
                    if not checker.find(
                        earliest_day=args.earliest_day,
                        latest_day=args.latest_day,
                        book=args.book,
                    ):
                        raise Exception("Unsuccessful attempt")
    else:
        checker.find(
            earliest_day=args.earliest_day, latest_day=args.latest_day, book=args.book
        )

    if args.book:
        checker.print_appointments()


if __name__ == "__main__":
    main()
