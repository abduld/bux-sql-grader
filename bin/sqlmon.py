#!/usr/bin/env python
import argparse
import logging
import MySQLdb
import time

log = logging.getLogger(__name__)


def expired_processes(db, db_blacklist=None, user_blacklist=None, limit=5):
    """ Generates a list of processes which have exceeded the execution limit.

        Returns a tuple of process ID and query.

        :param db: MySQLdb connection object
        :param db_blacklist: list of databases to monitor
        :param user_blacklist: list of users to monitor queries of
        :param limit: kill queries not finished in this many seconds

    """
    db.query("SHOW FULL PROCESSLIST")
    process_list = db.store_result().fetch_row(maxrows=500, how=1)

    for row in process_list:
        if row['Info']:
            log.debug("Process row: %s", row)

            # Skip queries to databases not in our blacklist
            if db_blacklist and row['db'] not in db_blacklist:
                log.debug("Skipping row, query database not in blacklist: %s",
                          db_blacklist)
                continue

            # Skip queries by users that are not in our blacklist
            if user_blacklist and row['User'] not in user_blacklist:
                log.debug("Skipping row, query user not in blacklist: %s",
                          user_blacklist)
                continue

            # Check if this query has been running for too long
            if row['Time'] > limit:
                yield row['Id'], row['Info']
            else:
                log.debug("Skipping row, execution time is under %d second limit", limit)


if __name__ == "__main__":

    # Command line options
    parser = argparse.ArgumentParser(description="Kills long running MySQL processes")
    parser.add_argument("--host", default="127.0.0.1", help="database host")
    parser.add_argument("--port", default=3306, type=int, help="database port")
    parser.add_argument("--user", default="root", help="database user")
    parser.add_argument("--password", default="", help="database password")
    parser.add_argument("--dbs", default=[], nargs="+", help="limit monitoring to specified databases")
    parser.add_argument("--users", default=[], nargs="+", help="limit monitoring to queries executed by these users")
    parser.add_argument("--limit", default=30, type=int, help="query execution limit in seconds")
    parser.add_argument("--loglevel", default="warning", help="python log level")
    args = parser.parse_args()

    # Log configuration
    logging.basicConfig(level=getattr(logging, args.loglevel.upper()),
                        format="%(asctime)s - %(levelname)s - %(message)s")

    db_list = "All"
    if args.dbs:
        db_list = ", ".join(args.dbs)

    user_list = "All"
    if args.users:
        user_list = ", ".join(args.users)

    print
    print "Monitoring MySQL server for long running queries."
    print
    print "Host: %s" % args.host
    print "Port: %s" % args.port
    print "User: %s" % args.user
    print "Databases to watch: %s" % db_list
    print "Users to watch: %s" % user_list
    print "Time limit: %ds" % args.limit
    print

    # Establish database connection
    db = MySQLdb.connect(user=args.user,
                         passwd=args.password,
                         host=args.host,
                         port=args.port)

    # Enter query monitoring loop
    try:
        while True:
            for pid, query in expired_processes(db=db,
                                                db_blacklist=args.dbs,
                                                user_blacklist=args.users,
                                                limit=args.limit):
                db.query("KILL %d" % pid)

                log.warning("Killed query #%d: %s (exceeded %ds execution limit)",
                            pid, query, args.limit)

            time.sleep(2)

    except (KeyboardInterrupt, SystemExit):
        pass

    db.close()

    print
    print "MySQL query monitor exiting."
    print
