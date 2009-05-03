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

# TODO: Rewrite scraping/REs using something more sane, like BeautifulSoup

import re
import sys
import time as time_module
import datetime
import sched
import string
import urllib
import urllib2
import httplib
import smtplib
import getpass
from HTMLParser import HTMLParser

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
main_url = 'www.southwest.com'
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
  def __init__(self, reservation):
    self.reservation = reservation

class Reservation(object):
  def __init__(self, first_name, last_name, code):
    self.first_name = first_name
    self.last_name = last_name
    self.code = code

# =========== function definitions =======================================

# this is a parser for the Southwest pages
class HTMLSouthwestParser(HTMLParser):

  def __init__(self, swdata):
    self._reset()
    HTMLParser.__init__(self)

    # if a web page string is passed, feed it
    if swdata != None and len(swdata)>0:
      self.feed(swdata)
      self.close()

  def _reset(self):
    self.hiddentags = {}
    self.searchaction = ""
    self.formaction = ""
    self.is_search = False
    self.textnames = []

  # override the feed function to reset our parameters
  # and then call the original feed function
  def feed(self, formdata):
    self._reset()
    HTMLParser.feed(self, formdata)

  # handle tags in web pages
  # this is where the real magic is done
  def handle_starttag(self, tag, attrs):
    if tag=="input":
      ishidden = False
      ischeckbox = False
      istext = False
      issubmit = False
      thevalue = ""
      thename = None
      for attr in attrs:
        if attr[0]=="type":
          if attr[1]=="hidden":
            ishidden= True
          elif attr[1]=="checkbox" or attr[1]=="radio":
            ischeckbox = True
          elif attr[1]=="text":
            istext = True
          elif attr[1]=="submit":
            issubmit = True
        elif attr[0]=="name":
          thename= attr[1]
          istext = True
        elif attr[0]=="value":
          thevalue= attr[1]

      # store the tag for search forms separately
      # from the tags for non-search forms
      if (ishidden or ischeckbox) and not self.is_search:
        self.hiddentags.setdefault(thename, []).append(thevalue)

      # otherwise, append the name of the text fields
      elif istext and not self.is_search and not issubmit:
        self.textnames.append(thename)

    elif tag=="form":
      for attr in attrs:
        if attr[0]=="action":
          theaction = attr[1]

          # check to see if this is a search form
          if theaction.find("search") > 0:
            self.searchaction = theaction
            self.is_search = True
          else:
            self.formaction = theaction
            self.is_search = False


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
  url = "http://%s%s" % (host, path)
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
  url = "http://%s%s" % (host, path)
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

# this routine extracts the departure date and time
def getFlightTimes(the_url, res):
  if DEBUG_SCH > 1:
    swdata = ReadFile("Southwest Airlines - Retrieve Itinerary.htm")
  else:
    swdata = ReadUrl(main_url, the_url)

  if swdata == None or len(swdata) == 0:
    print "Error: no data returned from ", main_url+the_url
    sys.exit(1)

  gh = HTMLSouthwestParser(swdata)

  # get the post action name from the parser
  post_url = gh.formaction
  if post_url == None or post_url == "":
    print "Error: no POST action found in ", main_url + the_url
    sys.exit(1)

  # load the parameters into the text boxes
  params = setInputBoxes(gh.textnames, res.code, res.first_name, res.last_name)

  # submit the request to pull up the reservations on this confirmation number
  if DEBUG_SCH > 1:
    reservations = ReadFile("Southwest Airlines - Schedule.htm")
  else:
    reservations = PostUrl(main_url, post_url, params)

  if reservations == None or len(reservations) == 0:
    print "Error: no data returned from ", main_url + post_url
    print "Params = ", dparams
    sys.exit(1)

  current_pos = 0
  res.flights = []

  # Find all of the flights listed on the page
  while True:
    # parse the returned file to grab the dates and times
    # the last word in the table above the first date is "Routing Details"
    # this is currently a unique word in the html returned by the above
    dateloc_0 = reservations.find("Details", current_pos)
    dateloc_1 = reservations.find("bookingFormText", dateloc_0)
    i1 = reservations.find(">", dateloc_1)
    i2 = reservations.find("<", i1)
    flight_date_str = reservations[i1 + 1:i2]

    # narrow down the search to the line with the word depart
    timeloc = reservations.find("Depart", dateloc_1)
    timeline = reservations[timeloc:timeloc+120]

    # use a regular expression to find the two times
    ts = re.findall("(\w\w\w)\) at (\d{1,2}\:\d{1,2}[apAP][mM])", timeline)
    if len(ts) < 2:
      break

    flight = Flight(res)
    flight.depart_airport = ts[0][0]
    flight.depart_tz = airport_timezone_map[flight.depart_airport]
    flight.arrive_airport = ts[1][0]
    flight.arrive_tz = airport_timezone_map[flight.arrive_airport]

    flight_depart_time = time(*time_module.strptime(ts[0][1], "%I:%M%p")[3:5])
    flight_arrive_time = time(*time_module.strptime(ts[1][1], "%I:%M%p")[3:5])

    flight_date = date(date.today().year,
                       *time_module.strptime(flight_date_str, "%b %d")[1:3])
    if flight_date - date.today() < timedelta(days=-300):
      flight_date = flight_date.replace(year=flight_date.year+1)

    depart_dt = flight.depart_tz.localize(
      datetime.combine(flight_date, flight_depart_time),
      is_dst=None)
    depart_dt_utc = depart_dt.astimezone(utc)
    arrive_dt = flight.arrive_tz.localize(
      datetime.combine(flight_date, flight_arrive_time),
      is_dst=None)
    arrive_dt_utc = arrive_dt.astimezone(utc)

    if arrive_dt_utc < depart_dt_utc:
      arrive_dt = flight.arrive_tz.normalize(
        arrive_dt.replace(day = arrive_dt.day+1))
      arrive_dt_utc = arrive_dt.astimezone(utc)

    flight.depart_dt = depart_dt
    flight.depart_dt_utc = depart_dt_utc
    flight.arrive_dt = arrive_dt
    flight.arrive_dt_utc = arrive_dt_utc
    res.flights.append(flight)

    current_pos = timeloc

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
  gh = HTMLSouthwestParser(swdata)

  # get the post action name from the parser
  post_url = gh.formaction
  if post_url==None or post_url=="":
    print "Error: no POST action found in ", main_url+the_url
    sys.exit(1)

  # load the parameters into the text boxes by name
  # where the names are obtained from the parser
  params = setInputBoxes(gh.textnames, res.code, res.first_name, res.last_name)

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
  rh = HTMLSouthwestParser(reservations)

  # Extract the name of the post function to check into the flight
  final_url = rh.formaction

  # the returned web page contains three unique security-related hidden fields
  # plus a dynamically generated value for the checkbox or radio button
  # these must be sent to the next submit post to work properly
  # they are obtained from the parser object
  params = rh.hiddentags
  if len(params) < 4:
    dlog("Error: Fewer than the expect 4 special fields returned from %s" % main_url+post_url)
    return None

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
  num = re.search(r"bpPassNum\"[^>]*>(\d+)", checkinresult)

  if group and num:
    return "%s%s" % (group.group(1), num.group(1))
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
          % (i+1, flight.depart_airport, DateTimeToString(flight.depart_dt),
             DateTimeToString(flight.depart_dt_utc),
             flight.arrive_airport, DateTimeToString(flight.arrive_dt),
             DateTimeToString(flight.arrive_dt_utc))
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
  
  try:
    smtp = smtplib.SMTP(smtp_server, 587)
    smtp.ehlo()
    if smtp_use_tls:
      smtp.starttls()
      smtp.ehlo()
    if smtp_auth:
      smtp.login(smtp_user, smtp_password)
    print "sending mail"
    for to in [string.strip(s) for s in string.split(email_to, ",")]:
      smtp.sendmail(email_from, email_to, """From: %s
To: %s
Subject: %s

%s
""" % (email_from, email_to, subject, message));
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

  global smtp_user, smtp_password, email_from, email_to
  
  if should_send_email:
    if not email_from:
      email_from = raw_input("Email from: ");
    if not email_to:
      email_to = raw_input("Email to: ");
    if not smtp_user:
      smtp_user = email_from
    if not smtp_password and smtp_auth:
      smtp_password = getpass.getpass("Email Password: ");

  sch = sched.scheduler(time_module.time, time_module.sleep)

  # get the departure times in a tuple
  for res in reservations:
    getFlightTimes(retrieve_url, res)

    # print some information to the terminal for confirmation purposes
    displayFlightInfo(res, res.flights, True)

    # Schedule all of the flights for checkin.  Schedule 3 minutes before our clock
    # says we are good to go
    for flight in res.flights:
      flight_time = time_module.mktime(flight.depart_dt_utc.utctimetuple()) - time_module.timezone
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
