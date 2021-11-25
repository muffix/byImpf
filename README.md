# ImpfChecker

Basic checker for Bavaria's booking portal for vaccination appointments. 
Checks the portal for the first available appointment and prints it. 

## Requirements

- You need to be registered with the portal at https://impfzentren.bayern/citizen/
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
You can find your citizen ID if you login to the portal and select the person. The address bar in your browser contains 
the ID in the following format: `https://impfzentren.bayern/citizen/overview/{CITIZEN_ID}`.

Minimal example to find the next available appointment:
```shell
python impf.py --citizen-id=AAAAAAAA-0000-0000-0000-AAAAAAAAAAAA --email=user@example.com --password=my_password
```

Full help: 
```
$ python impf.py -h                                                                                                                                                                                                                                                                Py byImpf 14:25:01
usage: impf.py [-h] --citizen-id CITIZEN_ID --email EMAIL --password PASSWORD [--earliest-day EARLIEST_DAY] [--book | --no-book]

Appointment checker and booker for Bavarian vaccination centres

optional arguments:
  -h, --help            show this help message and exit
  --citizen-id CITIZEN_ID
                        Your citizen ID. Find it in the address bar of your browser after selecting the person in the web portal.
  --email EMAIL         Your login email address
  --password PASSWORD   Your login password
  --earliest-day EARLIEST_DAY
                        The earliest day from which to find an appointment, in ISO format (YYYY-MM-DD)
  --book, --no-book     Whether to book the appointment if found (default: False)
```
