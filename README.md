# ImpfChecker

Basic checker for Bavaria's booking portal for vaccination appointments.
Checks the portal for the first available appointment and prints it.

## Requirements

- You need to be registered with the [vaccination portal](https://impfzentren.bayern/citizen/)
- You need to have selected a vaccination centre in the portal
- Python 3

## How to run

### Install the dependencies

Just run

```shell
pip install -r requirements.txt
```

### Run the checker

The checker requires your username, password, and citizen ID.
You can find your citizen ID if you login to the portal and select the person.
The address bar in your browser contains the ID in the following format:
`https://impfzentren.bayern/citizen/overview/{CITIZEN_ID}`.

Minimal example to find the next available appointment:

```shell
python byimpf.py --citizen-id=AAAAAAAA-0000-0000-0000-AAAAAAAAAAAA --email=user@example.com --password=my_password
```

You can additionally pass `--earliest-day` with the earliest acceptable date,
which restricts the search to appointments after that date:

```shell
python byimpf.py --citizen-id=AAAAAAAA-0000-0000-0000-AAAAAAAAAAAA --email=user@example.com --password=my_password --earliest-day=2021-12-24
```

Full help:

```text
$ python impf.py -h                                                                                                                                                                                                                                                                Py byImpf 14:25:01
usage: impf.py [-h] --citizen-id CITIZEN_ID --email EMAIL --password PASSWORD [--earliest-day EARLIEST_DAY] [--latest-day LATEST_DAY] [--interval INTERVAL] [--book | --no-book]

Appointment checker and booker for Bavarian vaccination centres

optional arguments:
  -h, --help            show this help message and exit
  --citizen-id CITIZEN_ID
                        Your citizen ID. Find it in the address bar of your browser after selecting the person in the web portal.
  --email EMAIL         Your login email address
  --password PASSWORD   Your login password
  --earliest-day EARLIEST_DAY
                        The earliest day from which to find an appointment, in ISO format (YYYY-MM-DD)
  --latest-day LATEST_DAY
                        The latest acceptable day for an appointment, in ISO format (YYYY-MM-DD)
  --interval INTERVAL   The interval in seconds between checks. If not passed, only one check is made.
  --book, --no-book     Whether to book the appointment if found (default: False)
```

#### Checking until successful

You can use the optional `--interval` option to tell the script to keep trying until it succeeds in finding (or booking
if `--book` is also passed). For example, with `--interval=60` an attempt is made every 60 seconds.

## Running in Docker

Alternatively, you can run the checker in a Docker container, passing some or all of the arguments listed above:

```shell
docker run --rm ghcr.io/muffix/byimpf --citizen-id=AAAAAAAA-0000-0000-0000-AAAAAAAAAAAA --email=user@example.com --password=my_password
```
