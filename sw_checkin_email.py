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
import cookielib
import urllib
import urllib2
import urlparse
import httplib
import smtplib
import getpass
from BeautifulSoup import BeautifulSoup
from BeautifulSoup import Tag

try:
  from email.mime.multipart import MIMEMultipart
  from email.mime.text import MIMEText
except:
  from email.MIMEMultipart import MIMEMultipart
  from email.MIMEText import MIMEText

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

# ========================================================================
# fixed page locations and parameters
base_url = 'https://www.southwest.com'
checkin_url = urlparse.urljoin(base_url, '/flight/retrieveCheckinDoc.html')
retrieve_url = urlparse.urljoin(base_url, '/flight/lookup-air-reservation.html')

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

class Error(Exception):
  pass

# ========================================================================

verbose = False
def dlog(str):
  if verbose:
    print "DEBUG: %s" % str

# ========================================================================

class Flight(object):
  def __init__(self):
    self.legs = []

class FlightLeg(object):
  pass

class FlightStop(object):
  pass

class Reservation(object):
  def __init__(self, first_name, last_name, code):
    self.first_name = first_name
    self.last_name = last_name
    self.code = code

# =========== function definitions =======================================

# build our cookie based opener
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())

# this function reads a URL and returns the text of the page
def ReadUrl(url):
  headers = {}
  headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
  headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.5; en-US; rv:1.9.2.8) Gecko/20100722 Firefox/3.6.8 GTB7.1'

  dlog("GET to %s" % url)
  dlog("  headers: %s" % headers)


  try:
    req = urllib2.Request(url=url, headers=headers)
    resp = opener.open(req)
  except Exception, e:
    raise Error("Cannot GET: %s" % url, e)

  return (resp.read(), resp.geturl())

# this function sends a post just like you clicked on a submit button
def PostUrl(url, params):
  str_params = urllib.urlencode(params, True)
  headers = {}
  headers['Content-Type'] = 'application/x-www-form-urlencoded'
  headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
  headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.5; en-US; rv:1.9.2.8) Gecko/20100722 Firefox/3.6.8 GTB7.1'

  dlog("POST to %s" % url)
  dlog("  data: %s" % str_params)
  dlog("  headers: %s" % headers)

  try:
    req = urllib2.Request(url=url, data=str_params, headers=headers)
    resp = opener.open(req)
  except Exception, e:
    raise Error('Cannot POST: %s' % url, e)

  return (resp.read(), resp.geturl())
  
def FindAllByTagClass(soup, tag, klass):
  return soup.findAll(tag, 
      attrs = { 'class': re.compile(re.escape(klass)) })

def FindByTagClass(soup, tag, klass):
  return soup.find(tag, 
      attrs = { 'class': re.compile(re.escape(klass)) })
      
def FindNextSiblingByTagClass(soup, tag, klass):
  return soup.findNextSibling(tag, 
      attrs = { 'class': re.compile(re.escape(klass)) })

class HtmlFormParser(object):
  class Input(object):
    def __init__(self, tag):
      self.type = tag.get("type", 'text')
      self.name = tag.get("name", '')
      self.value = tag.get("value", '')
      # default checked to true for hidden and text inputs
      default_checked = not(self.type == 'checkbox' or self.type == 'radio' 
          or self.type == 'submit')
      self.checked = tag.get("checked", default_checked)
      
    def __str__(self):
      return repr(self.__dict__)
      
    def addToParams(self, params):
      if self.checked:
        params.append((self.name, self.value))
      
  def __init__(self, data, page_url, id):
    self.inputs = []
    self.formaction = ""

    soup = BeautifulSoup(data)
    form = soup.find("form", id=id)
    if not form:
      return

    self.formaction = form.get("action", None)
    self.submit_url = urlparse.urljoin(page_url, self.formaction)

    # find all inputs
    for i in form.findAll("input"):
      input = HtmlFormParser.Input(i)
      if input.name:
        self.inputs.append(input)
          
  def submit(self):
    """Submit the form and return the (contents, url)."""
    return PostUrl(self.submit_url, self.getParams())
          
  def validateSubmitButtons(self):
    """Ensures that one and only one submit is 'checked'."""
    numChecked = 0
    for i in self.inputs:
      if i.type == 'submit' and i.checked:
        numChecked += 1
    if numChecked > 1:
      raise Error('Too many submit buttons checked on form!')
    
    # None checked, default to the first one
    if numChecked == 0:
      for i in self.inputs:
        if i.type == 'submit':
          i.checked = True
          break
  
  def setSubmit(self, name, value=None):
    for i in self.inputs:
      if i.type == 'submit' and i.name == name:
        if value == None or i.value == value:
          i.checked = True
          break
  
  def getParams(self):
    self.validateSubmitButtons()
    params = []
    for i in self.inputs:
      i.addToParams(params)
    return params
    
  def setTextField(self, name, value):
    for i in self.inputs:
      if i.type == 'text' and i.name == name:
        i.value = value
        break
    
  def setAllCheckboxes(self, name):
    for i in self.inputs:
      if i.type == 'checkbox' and i.name == name:
        cb.checked = True
        break

class FlightInfoParser(object):
  def __init__(self, data):
    soup = BeautifulSoup(data)
    self.flights = []
    for td in FindAllByTagClass(soup, "td", "flightInfoDetails"):
      self.flights.append(self._parseFlightInfo(td))

  def _parseFlightInfo(self, soup):
    flight = Flight()

    flight_date_str = FindByTagClass(soup, "span", "travelDateTime").string
    day = date(*time_module.strptime(flight_date_str, "%A, %B %d, %Y")[0:3])

    td = FindNextSiblingByTagClass(soup, "td", "flightRouting")
    
    tr = td.find("tr")
    while tr:
      flight_leg = FlightLeg()
      flight.legs.append(flight_leg)
      flight_leg.depart = self._parseFlightStop(day, tr)
      tr = tr.findNextSibling("tr")
      flight_leg.arrive = self._parseFlightStop(day, tr)

      if flight_leg.arrive.dt_utc < flight_leg.depart.dt_utc:
        flight_leg.arrive.dt = flight_leg.arrive.tz.normalize(
          flight_leg.arrive.dt.replace(day = flight_leg.arrive.dt.day+1))
        flight_leg.arrive.dt_utc = flight_leg.arrive.dt.astimezone(utc)

      tr = tr.findNextSibling("tr")
 
    return flight

  def _parseFlightStop(self, day, soup):
    flight_stop = FlightStop()
    stop_td = FindByTagClass(soup, "td", "routingDetailsStops")
    s = ''.join(stop_td.findAll(text=True))
    flight_stop.airport = re.findall("\(([A-Z]{3})\)", s)[0]
    flight_stop.tz = airport_timezone_map[flight_stop.airport]
    
    detail_td = FindByTagClass(soup, "td", "routingDetailsTimes")
    s = ''.join(detail_td.findAll(text=True)).strip()
    flight_time = time(*time_module.strptime(s, "%I:%M %p")[3:5])
    flight_stop.dt = flight_stop.tz.localize(
      datetime.combine(day, flight_time), is_dst=None)
    flight_stop.dt_utc = flight_stop.dt.astimezone(utc)
    return flight_stop
    

# this routine extracts the departure date and time
def getFlightTimes(res):
  (swdata, form_url) = ReadUrl(retrieve_url)

  form = HtmlFormParser(swdata, form_url, "pnrFriendlyLookup_check_form")

  # load the parameters into the text boxes
  form.setTextField('confirmationNumberFirstName', res.first_name)
  form.setTextField('confirmationNumberLastName', res.last_name)
  form.setTextField('confirmationNumber', res.code)

  # submit the request to pull up the reservations on this confirmation number
  (reservations, _) = form.submit()

  flights = FlightInfoParser(reservations)
  res.flights = flights.flights

  return res.flights

def getBoardingPass(res):
  # read the southwest checkin web site
  (swdata, form_url) = ReadUrl(checkin_url)

  # parse the data
  form = HtmlFormParser(swdata, form_url, "itineraryLookup")

  # load the parameters into the text boxes by name
  # where the names are obtained from the parser
  form.setTextField('confirmationNumber', res.code)
  form.setTextField('firstName', res.first_name)
  form.setTextField('lastName', res.last_name)

  # submit the request to pull up the reservations
  (reservations, form_url) = form.submit()
    
  # parse the returned reservations page
  form = HtmlFormParser(reservations, form_url, "checkinOptions")
  
  # Need to check all of the passengers
  for i in form.inputs:
    if i.type == 'checkbox' and i.name.startswith('checkinPassengers'):
      i.checked = True
  
  # This is the button to press
  form.setSubmit('printDocuments')

  # finally, lets check in the flight and make our success file
  (checkinresult, form_url) = form.submit()

  soup = BeautifulSoup(checkinresult)
  pos_boxes = FindAllByTagClass(soup, 'div', 'boardingPosition')
  pos = []
  for box in pos_boxes:
    group = None
    group_img = FindByTagClass(box, 'img', 'group')
    if group_img:
      group = group_img['alt']
    num = 0
    for num_img in FindAllByTagClass(box, 'img', 'position'):
      num *= 10
      num += int(num_img['alt'])
    pos.append("%s%d" % (group, num))

  # Add a base tag to the soup
  tag = Tag(soup, 'base', [('href', urlparse.urljoin(form_url, "."))])
  soup.head.insert(0, tag)

  return (", ".join(pos), str(soup))

def DateTimeToString(time):
  return time.strftime("%I:%M%p %b %d %y %Z");

# print some information to the terminal for confirmation purposes
def getFlightInfo(res, flights):
  message = ""
  message += "Confirmation number: %s\r\n" % res.code
  message += "Passenger name: %s %s\r\n" % (res.first_name, res.last_name)

  for (i, flight) in enumerate(flights):
    message += "Flight %d:\n" % (i+1, )
    for leg in flight.legs:
      message += "  Departs: %s %s (%s)\n  Arrives: %s %s (%s)\n" \
          % (leg.depart.airport, DateTimeToString(leg.depart.dt),
             DateTimeToString(leg.depart.dt_utc),
             leg.arrive.airport, DateTimeToString(leg.arrive.dt),
             DateTimeToString(leg.arrive.dt_utc))
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
  (position, boarding_pass) = getBoardingPass(res)
  if position:
    message = ""
    message += "SUCCESS.  Checked in at position %s\r\n" % position
    message += getFlightInfo(res, [flight])
    print message
    send_email("Flight checked in!", message, boarding_pass)
  else:
    if attempt > (CHECKIN_WINDOW * 2) / RETRY_INTERVAL:
      print "FAILURE.  Too many failures, giving up."
    else:
      print "FAILURE.  Scheduling another try in %d seconds" % RETRY_INTERVAL
      sch.enterabs(time_module.time() + RETRY_INTERVAL, 1,
                   TryCheckinFlight, (res, flight, sch, attempt + 1))
      
def send_email(subject, message, boarding_pass = None):
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
      msg = MIMEMultipart("mixed")
      msg['Subject'] = subject
      msg['To'] = to
      msg['From'] = email_from
      msg.attach(MIMEText(message, 'plain'))
      if boarding_pass:
        msg_bp = MIMEText(boarding_pass, 'html')
        msg_bp.add_header('content-disposition', 'attachment', filename='boarding_pass.html')
        msg.attach(msg_bp)
      smtp.sendmail(email_from, to, msg.as_string())
      
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
    getFlightTimes(res)

    # print some information to the terminal for confirmation purposes
    displayFlightInfo(res, res.flights, True)

    # Schedule all of the flights for checkin.  Schedule 3 minutes before our clock
    # says we are good to go
    for flight in res.flights:
      flight_time = time_module.mktime(flight.legs[0].depart.dt_utc.utctimetuple()) - time_module.timezone
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
