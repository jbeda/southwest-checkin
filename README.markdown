# Southwest Checkin Script #

----

**Warning:** This script is old and out of date. Since it was written southwest has updated their site.  If you get it working again I'm happy to take patches or point any users to an updated version.

----

This is a command line python script that will, given a confirmation code and
passenger name, will do the following:

* Look up flight info and display when the flights leave and where they are
  going.
* Wait until 24 hours the first flight
* Drive the web site to check in all users for that reservation.
* Optionally send email with the boarding pass as an attachment
* Repeat with any unchecked in flights

If you don't have the script email you, you will still need to go back to the
southwest site to print your boarding pass, but you should have a decent place
in line.

If things look broken, please let me know and I'll try to fix it. Most of the
time it is hard to fix the script without an active reservation though so
letting me know in that 24 hour period with your confirmation code is probably
the best way to keep the script working.

You can let me know by sending email to joe.github@bedafamily.com. Hopefully
that address won't be completely spammed up.

## Installation ##

This scripts depends on a couple of other python libraries. The easiest way to
install is to use easy_install.

    $ easy_install BeautifulSoup
    $ easy_install pytz

## Usage ##

    $ sw_checkin_email.py John Doe ABC123

You will have to leave your terminal open while the script is waiting. You may
want to look into using [nohup or disown](http://www.basicallytech.com/blog/index.php?/archives/70-Shell-stuff-job-control-and-screen.html#bash_disown)
so that you can log out while the script runs.
