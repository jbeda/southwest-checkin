#! /usr/bin/python

# The MIT License
#
# Copyright (c) 2008 Joe Beda
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# Based on script by Ken Washington
#   http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/496790

import re
import sys
import time as time_module
import datetime
import sched
import string
import urllib
import urllib2
import urlparse
import httplib
import smtplib
import getpass
from BeautifulSoup import BeautifulSoup

from datetime import datetime,date,timedelta,time
from pytz import timezone,utc

# If we are unable to check in, how soon should we retry?
RETRY_INTERVAL = 5

# How soon before the designated time should we try to check in?
CHECKIN_WINDOW = 3*60

# Email confuration
should_send_email = True
email_from = None
email_to = None

# SMTP server config
if False:  # local config
  smtp_server = "localhost"
  smtp_auth = False
  smtp_user = email_from
  smtp_password = ""  # if blank, we will prompt first and send test message       
  smtp_use_tls = False
else:  # gmail config
  smtp_server = "smtp.gmail.com"
  smtp_auth = True
  smtp_user = email_from
  smtp_password = ""  # if blank, we will prompt first and send test message
  smtp_use_tls = True

DEBUG_SCH = 0

# ========================================================================
# fixed page locations and parameters
# DO NOT change these parameters
main_url = 'http://www.southwest.com'
checkin_url = '/travel_center/retrieveCheckinDoc.html'
retrieve_url = '/travel_center/retrieveItinerary.html'
defaultboxes = ["recordLocator", "firstName", "lastName"]

# ========================================================================

# Common US time zones
tz_alaska = timezone('US/Alaska')
tz_aleutian = timezone('US/Aleutian')
tz_arizona = timezone('US/Arizona')
tz_central = timezone('US/Central')
tz_east_indiana = timezone('US/East-Indiana')
tz_eastern = timezone('US/Eastern')
tz_hawaii = timezone('US/Hawaii')
tz_indiana_starke = timezone('US/Indiana-Starke')
tz_michigan = timezone('US/Michigan')
tz_mountain = timezone('US/Mountain')
tz_pacific = timezone('US/Pacific')

airport_timezone_map = {
  'ABQ': tz_mountain,
  'ALB': tz_eastern,
  'AMA': tz_central,
  'AUS': tz_central,
  'BDL': tz_eastern,
  'BHM': tz_central,
  'BNA': tz_central,
  'BOI': tz_mountain,
  'BUF': tz_eastern,
  'BUR': tz_pacific,
  'BWI': tz_eastern,
  'CLE': tz_eastern,
  'CMH': tz_eastern,
  'CRP': tz_central,
  'DAL': tz_central,
  'DEN': tz_mountain,
  'DTW': tz_eastern,
  'ELP': tz_mountain,
  'FLL': tz_eastern,
  'GEG': tz_pacific,
  'HOU': tz_central,
  'HRL': tz_central,
  'IAD': tz_eastern,
  'IND': tz_eastern,
  'ISP': tz_eastern,
  'JAN': tz_eastern,
  'JAX': tz_eastern,
  'LAS': tz_pacific,
  'LAX': tz_pacific,
  'LBB': tz_central,
  'LIT': tz_central,
  'MAF': tz_central,
  'MCI': tz_central,
  'MCO': tz_eastern,
  'MDW': tz_central,
  'MHT': tz_eastern,
  'MSP': tz_central,
  'MSY': tz_central,
  'OAK': tz_pacific,
  'OKC': tz_central,
  'OMA': tz_central,
  'ONT': tz_pacific,
  'ORF': tz_eastern,
  'PBI': tz_eastern,
  'PDX': tz_pacific,
  'PHL': tz_eastern,
  'PHX': tz_arizona,
  'PIT': tz_eastern,
  'PVD': tz_eastern,
  'RDU': tz_eastern,
  'RNO': tz_pacific,
  'RSW': tz_eastern,
  'SAN': tz_pacific,
  'SAT': tz_central,
  'SDF': tz_eastern,
  'SEA': tz_pacific,
  'SFO': tz_pacific,
  'SJC': tz_pacific,
  'SLC': tz_mountain,
  'SMF': tz_pacific,
  'SMF': tz_pacific,
  'SNA': tz_pacific,
  'STL': tz_central,
  'TPA': tz_eastern,
  'TUL': tz_central,
  'TUS': tz_arizona,
}

# ========================================================================

verbose = False
def dlog(str):
  if verbose:
    print "DEBUG: %s" % str

# ========================================================================

class Flight(object):
  pass

class FlightStop(object):
  pass

class Reservation(object):
  def __init__(self, first_name, last_name, code):
    self.first_name = first_name
    self.last_name = last_name
    self.code = code

# =========== function definitions =======================================

def WriteFile(filename, data):
  fd = open(filename, "w")
  fd.write(data)
  fd.close()

def ReadFile(filename):
  fd = open(filename, "r")
  data = fd.read()
  fd.close()

# this function reads a URL and returns the text of the page
def ReadUrl(host, path):
  url = urlparse.urljoin(host, path)
  dlog("GET to %s" % url)
  wdata = ""

  try:
    req = urllib2.Request(url=url)
    resp = urllib2.urlopen(req)
  except:
    print "Error: Cannot connect in GET mode to ", url
    sys.exit(1)

  wdata = resp.read()

  return wdata

# this function sends a post just like you clicked on a submit button
def PostUrl(host, path, dparams):
  wdata = ""
  url = urlparse.urljoin(host, path)
  params = urllib.urlencode(dparams, True)
  headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}

  dlog("POST to %s" % url)
  dlog("  data: %s" % params)
  dlog("  headers: %s" % headers)

  try:
    req = urllib2.Request(url=url, data=params, headers=headers)
    resp = urllib2.urlopen(req)
  except:
    print "Error: Cannot connect in POST mode to ", url
    print "Params = ", dparams
    print sys.exc_info()[1]
    sys.exit(1)

  wdata = resp.read()

  return wdata

def setInputBoxes(textnames, conf_number, first_name, last_name):
  if len(textnames) == 3:
    boxes = textnames
  else:
    boxes = defaultboxes

  params = {}
  params[boxes[0]] = conf_number
  params[boxes[1]] = first_name
  params[boxes[2]] = last_name

  return params

class HtmlFormParser(object):
  def __init__(self, data, id):
    self.hiddentags = {}
    self.formaction = ""
    self.textnames = []

    soup = BeautifulSoup(data)
    form = soup.find("form", id=id)
    if not form:
      return

    self.formaction = form.get("action", None)

    # find all inputs
    for i in form.findAll("input"):
      self.addInput(i)

  def addInput(self, input):
    type = input.get("type", None)
    name = input.get("name", None)
    if type == "hidden" or type == "checkbox" or type == "radio" :
      self.hiddentags.setdefault(name, []).append(input.get("value", None))
    elif type == "text":
      self.textnames.append(name);

class FlightInfoParser(object):
  def __init__(self, data):
    soup = BeautifulSoup(data)
    self.flights = []

    for td in soup.findAll("td", "flightInfoDetails"):
      self.flights.append(self._parseFlightInfo(td))

  def _parseFlightInfo(self, soup):
    flight = Flight()

    flight_date_str = soup.find("span", "travelDateTime").string
    day = date(*time_module.strptime(flight_date_str, "%A, %B %d, %Y")[0:3])

    td = soup.findNextSibling("td", "flightRouting")
    tr = td.find("tr")
    flight.depart = self._parseFlightStop(day, tr)
    tr = tr.findNextSibling("tr")
    flight.arrive = self._parseFlightStop(day, tr)

    if flight.arrive.dt_utc < flight.depart.dt_utc:
      flight.arrive.dt = flight.arrive.tz.normalize(
        flight.arrive.dt.replace(day = flight.arrive.dt.day+1))
      flight.arrive.dt_utc = flight.arrive.dt.astimezone(utc)
    return flight

  def _parseFlightStop(self, day, soup):
    flight_stop = FlightStop()
    s = soup.find("td", attrs = {'class': re.compile("routingDetailsStops ?")}) \
        .find("strong").string
    flight_stop.airport = re.findall("\((\w\w\w)\)$", s)[0]
    flight_stop.tz = airport_timezone_map[flight_stop.airport]
    
    s = soup.find("td", attrs = {'class': re.compile("routingDetailsTimes ?")}) \
        .find("strong").string
    flight_time = time(*time_module.strptime(s, "%I:%M %p")[3:5])
    flight_stop.dt = flight_stop.tz.localize(
      datetime.combine(day, flight_time), is_dst=None)
    flight_stop.dt_utc = flight_stop.dt.astimezone(utc)
    return flight_stop
    

# this routine extracts the departure date and time
def getFlightTimes(the_url, res):
  if DEBUG_SCH > 1:
    swdata = ReadFile("Southwest Airlines - Retrieve Itinerary.htm")
  else:
    swdata = ReadUrl(main_url, the_url)

  if swdata == None or len(swdata) == 0:
    print "Error: no data returned from ", main_url+the_url
    sys.exit(1)

  form_data = HtmlFormParser(swdata, "itineraryLookup")

  # get the post action name from the parser
  post_url = form_data.formaction
  if post_url == None or post_url == "":
    print "Error: no POST action found in ", main_url + the_url
    sys.exit(1)

  # load the parameters into the text boxes
  params = setInputBoxes(form_data.textnames, res.code, res.first_name, res.last_name)

  # submit the request to pull up the reservations on this confirmation number
  if DEBUG_SCH > 1:
    reservations = ReadFile("Southwest Airlines - Schedule.htm")
  else:
    reservations = PostUrl(main_url, post_url, params)

  if reservations == None or len(reservations) == 0:
    print "Error: no data returned from ", main_url + post_url
    print "Params = ", dparams
    sys.exit(1)

  flights = FlightInfoParser(reservations)
  res.flights = flights.flights

  return res.flights

def getBoardingPass(the_url, res):
  # read the southwest checkin web site
  if DEBUG_SCH > 1:
    swdata = ReadFile("Southwest Airlines - Check In and Print Boarding Pass.htm")
  else:
    swdata = ReadUrl(main_url, the_url)

  if swdata==None or len(swdata)==0:
    print "Error: no data returned from ", main_url+the_url
    sys.exit(1)

  # parse the data
  form_data = HtmlFormParser(swdata, "itineraryLookup")

  # get the post action name from the parser
  post_url = form_data.formaction
  if post_url==None or post_url=="":
    print "Error: no POST action found in ", main_url+the_url
    sys.exit(1)

  # load the parameters into the text boxes by name
  # where the names are obtained from the parser
  params = setInputBoxes(form_data.textnames, 
                         res.code, res.first_name, 
                         res.last_name)

  # submit the request to pull up the reservations
  if DEBUG_SCH > 1:
    reservations = ReadFile("Southwest Airlines - Print Boarding Pass.htm")
  else:
    reservations = PostUrl(main_url, post_url, params)

  if reservations==None or len(reservations)==0:
    print "Error: no data returned from ", main_url+post_url
    print "Params = ", params
    sys.exit(1)

  # parse the returned reservations page
  form_data = HtmlFormParser(reservations, "checkinOptions")

  # Extract the name of the post function to check into the flight
  final_url = form_data.formaction

  params = form_data.hiddentags
  if len(params) < 2:
    dlog("Error: Fewer than the expect 2 special fields returned from %s" % main_url+post_url)
    return None
    
  # This is the button to press
  params.setdefault("printDocuments", []).append("Print Selected Document(s)")

  # finally, lets check in the flight and make our success file
  if DEBUG_SCH > 1:
    checkinresult = ReadFile("Southwest Airlines - Retrieve-Print Boarding Pass.htm")
  else:
    checkinresult = PostUrl(main_url, final_url, params)

  # write the returned page to a file for later inspection
  if checkinresult==None or len(checkinresult)==0:
    dlog("Error: no data returned from %s" % main_url+final_url)
    return None

  # always save the returned file for later viewing
  # TODO: don't clobber files when we have multiple flights to check in
  WriteFile("boardingpass.htm", checkinresult)

  # look for what boarding letter and number we got in the file
  group = re.search(r"boarding([ABC])\.gif", checkinresult)
  num = 0
  for m in re.finditer(r"boarding(\d)\.gif", checkinresult):
    num *= 10
    num += int(m.group(1))

  if group and num:
    return "%s%d" % (group.group(1), num)
  else:
    return None

def DateTimeToString(time):
  return time.strftime("%I:%M%p %b %d %y %Z");

# print some information to the terminal for confirmation purposes
def getFlightInfo(res, flights):
  message = ""
  message += "Confirmation number: %s\r\n" % res.code
  message += "Passenger name: %s %s\r\n" % (res.first_name, res.last_name)

  for (i, flight) in enumerate(flights):
    message += "Flight %d:\n  Departs: %s %s (%s)\n  Arrives: %s %s (%s)\n" \
          % (i+1, flight.depart.airport, DateTimeToString(flight.depart.dt),
             DateTimeToString(flight.depart.dt_utc),
             flight.arrive.airport, DateTimeToString(flight.arrive.dt),
             DateTimeToString(flight.arrive.dt_utc))
  return message

def displayFlightInfo(res, flights, do_send_email=False):
  message = getFlightInfo(res, flights)
  print message
  if do_send_email:
    send_email("Waiting for SW flight", message);

def TryCheckinFlight(res, flight, sch, attempt):
  print "-="*30
  print "Trying to checkin flight at %s" % DateTimeToString(datetime.now(utc))
  print "Attempt #%s" % attempt
  displayFlightInfo(res, [flight])
  position = getBoardingPass(checkin_url, res)
  if position:
    message = ""
    message += "SUCCESS.  Checked in at position %s\r\n" % position
    message += getFlightInfo(res, [flight])
    print message
    send_email("Flight checked in!", message)
  else:
    if attempt > (CHECKIN_WINDOW * 2) / RETRY_INTERVAL:
      print "FAILURE.  Too many failures, giving up."
    else:
      print "FAILURE.  Scheduling another try in %d seconds" % RETRY_INTERVAL
      sch.enterabs(time_module.time() + RETRY_INTERVAL, 1,
                   TryCheckinFlight, (res, flight, sch, attempt + 1))
      
def send_email(subject, message):
  if not should_send_email:
    return
  
  for to in [string.strip(s) for s in string.split(email_to, ",")]:
    try:
      smtp = smtplib.SMTP(smtp_server, 587)
      smtp.ehlo()
      if smtp_use_tls:
        smtp.starttls()
      smtp.ehlo()
      if smtp_auth:
        smtp.login(smtp_user, smtp_password)
      print "Sending mail to %s." % to
      smtp.sendmail(email_from, to, """From: %s
To: %s
Subject: %s

%s
""" % (email_from, to, subject, message))
      
      print "EMail sent successfully."
      smtp.close()
    except:
      print "Error sending email!"
      print sys.exc_info()[1]

# main program
def main():
  if (len(sys.argv) - 1) % 3 != 0 or len(sys.argv) < 4:
    print "Please provide name and confirmation code:"
    print "   %s (<firstname> <lastname> <confirmation code>)+" % sys.argv[0]
    sys.exit(1)

  reservations = []

  args = sys.argv[1:]
  while len(args):
    (firstname, lastname, code) = args[0:3]
    reservations.append(Reservation(firstname, lastname, code))
    del args[0:3]

  global smtp_user, smtp_password, email_from, email_to, should_send_email
  
  if should_send_email:
    if not email_from:
      email_from = raw_input("Email from: ");
    if email_from:
      if not email_to:
        email_to = raw_input("Email to: ");
      if not smtp_user:
        smtp_user = email_from
      if not smtp_password and smtp_auth:
        smtp_password = getpass.getpass("Email Password: ");
    else:
      should_send_email = False

  sch = sched.scheduler(time_module.time, time_module.sleep)

  # get the departure times in a tuple
  for res in reservations:
    getFlightTimes(retrieve_url, res)

    # print some information to the terminal for confirmation purposes
    displayFlightInfo(res, res.flights, True)

    # Schedule all of the flights for checkin.  Schedule 3 minutes before our clock
    # says we are good to go
    for flight in res.flights:
      flight_time = time_module.mktime(flight.depart.dt_utc.utctimetuple()) - time_module.timezone
      if flight_time < time_module.time():
        print "Flight already left!"
      else:
        sched_time = flight_time - CHECKIN_WINDOW - 24*60*60
        print "Update Sched: %s" % DateTimeToString(datetime.fromtimestamp(sched_time, utc))
        sch.enterabs(sched_time, 1, TryCheckinFlight, (res, flight, sch, 1))
    
  print "Current time: %s" % DateTimeToString(datetime.now(utc))
  print "Flights scheduled.  Waiting..."
  sch.run()

if __name__=='__main__':
  main()
