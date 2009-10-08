# Southwest Checkin Script #

This is a command line python script that will, given a confirmation code and
passenger name, will do the following:

* Look up flight info and display when the flights leave and where they are
  going.
* Wait until 24 hours the first flight
* Drive the web site to check in all users for that reservation.
* Optionally send email
* Repeat with any unchecked in flights

You will still need to go back to the southwest site to print your boarding
pass, but you should have a decent place in line.

## Installation ##

This scripts depends on a couple of other python libraries. The easiest way to
install is to use easy_install.

    $ easy_install BeautifulSoup
    $ easy_install pytz

## Usage ##

    $ sw_checkin_email.py John Doe ABC123

You will have to leave your terminal open while the script is waiting. You may
want to look into using [[nohup ordisown](http://www.basicallytech.com/blog/index.php?/archives/70-Shell-stuff-job-control-and-screen.html#bash_disown)
so that you can log out while the script runs.
