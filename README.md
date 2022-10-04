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
You can find your citizen ID if you log in to the portal and select the person.
The address bar in your browser contains the ID in the following format:
`https://impfzentren.bayern/citizen/overview/{CITIZEN_ID}`.

By default, it searches for the earliest available appointment for a boost dose with
any available vaccine. You can customise this with the options described below.

Minimal example to find the next available appointment:

```shell
python impf.py --citizen-id=AAAAAAAA-0000-0000-0000-AAAAAAAAAAAA --email=user@example.com --password=my_password
```

You can additionally pass `--earliest-day` with the earliest acceptable date,
which restricts the search to appointments after that date:

```shell
python impf.py --citizen-id=AAAAAAAA-0000-0000-0000-AAAAAAAAAAAA --email=user@example.com --password=my_password --earliest-day=2021-12-24
```

Full help:

```text
$ python impf.py -h                                                                                                                                                                                                                                                                Py byImpf 14:25:01
usage: impf.py [-h] --citizen-id CITIZEN_ID --email EMAIL --password PASSWORD [--earliest-day EARLIEST_DAY] [--latest-day LATEST_DAY] [--interval INTERVAL] [--book | --no-book]

Appointment checker and booker for Bavarian vaccination centres

options:
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
  --debug               Whether to print debug log output
  --dose DOSE           Which vaccination to looking for: first, second or boost. Defaults to boost.
  --first-vaccine-id FIRST_VACCINE_ID
                        The ID of the vaccine that was used for the first jab. Only required for the second vaccination.
  --variant VARIANT     Variants to find vaccines for; either ba1 or ba45. Leave blank for any.
```

#### Vaccine IDs

If you're looking for an appointment for the second vaccination, you need to specify the vaccine that was used for the
first jab. In addition to `--dose=second`, add `--first-vaccine-id` according to the following table. E.g.,
`--first-vaccine-id=002` if the first jab was BioNTech/Pfizer.

| Vaccine                                             | ID  |
|-----------------------------------------------------|:---:|
| Vaxzevria/AstraZeneca                               | 001 |
| Comirnaty (BioN-Tech/Pfizer)                        | 002 |
| Moderna COVID19 Vaccine                             | 003 |
| COVID-19 Vaccine Janssen                            | 005 |
| Nuvaxovid                                           | 006 |
| Valneva                                             | 008 |
| Comirnaty Original/Omicron BA.1 (BioNTech/Pfizer)   | 009 |
| Spikevax 0 (Zero)/O (Omicron) (Moderna)             | 010 |
| Comirnaty Original/Omicron BA.4-5 (BioNTech/Pfizer) | 011 |

#### Checking until successful

You can use the optional `--interval` option to tell the script to keep trying until it succeeds in finding (or booking
if `--book` is also passed). For example, with `--interval=60` an attempt is made every 60 seconds.

## Running in Docker

Alternatively, you can run the checker in a Docker container, passing some or all of the arguments listed above:

```shell
docker run --rm ghcr.io/muffix/byimpf --citizen-id=AAAAAAAA-0000-0000-0000-AAAAAAAAAAAA --email=user@example.com --password=my_password
```
