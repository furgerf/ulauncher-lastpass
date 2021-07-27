import logging
import subprocess
import re
import json
from memoization import cached
from lastpass.errors import LastPassError
logger = logging.getLogger(__name__)


class Lastpass:
    """ Class that interacts with LastPass CLI """
    def get_passwords(self, query):
        # --basic-regexp: case insensitive search
        # --expand-multi: always get back JSON
        cmd = "lpass show --json --expand-multi --basic-regexp %s" % query

        result = self.lpass(cmd)

        if result.return_code != 0:
            return self.handle_errors(result.output)

        return self.parse_list_results(query, result.output)

    def parse_list_results(self, query, output):
        """ Parses the LastPass response """

        site_data = json.loads(output)

        # lpass seems to return every entry where at least one of the parts of the query matches
        # however, multiple query parts are used to _restrict_ the results, so only keep the entries
        # that contain _all_ parts of the query
        result = [{
            'id': item["id"],
            'name': item["name"].replace("&", "&amp;"),
            'folder': item["group"]
        } for item in site_data if all(q.lower() in item["name"].lower() for q in query.split(" "))]
        return result

    def get_item(self, id):
        """ Returns a single item from LastPass vault with the specified id """
        cmd = "lpass show %s --json" % id

        result = self.lpass(cmd)

        if result.return_code != 0:
            return self.handle_errors(result.output)

        data = json.loads(result.output)
        site = data[0]

        is_note = False

        if site["note"] and not site["password"]:
            is_note = True

        return {
            "id": site["id"],
            "name": site["name"] or "",
            "url": site["url"] or "",
            "username": site["username"] or "",
            "password": site["password"] or "",
            "note": site["note"],
            "is_note": is_note
        }

    def handle_errors(self, output):
        """ Handles LastPass command line errors """

        if "Error: Could not find specified account(s)." in output:
            return []

        logger.error("LastPass Error: %s", output)
        raise LastPassError(output)

    @cached(ttl=15)
    def is_cli_installed(self):
        """ Checks if the lastpass cli is installed """
        p = subprocess.Popen(["which", "lpass"])
        p.communicate()

        if p.returncode != 0:
            return False

        return True

    @cached(ttl=15)
    def is_authenticated(self):
        """ Checks if the user is Authenticated in LastPass """
        result = self.lpass("lpass status")

        if "Logged in as" in result.output:
            return True

        return False

    def lpass(self, cmd):
        """ Runs the specified command on using lpass cli and return the rsult """

        p = subprocess.Popen(cmd,
                             shell=True,
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE)

        stdout, stderr = p.communicate()

        stdout = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')

        if stdout and stderr:
            output = "%s / %s" % (stdout, stderr)
        elif stdout:
            output = stdout
        else:
            output = stderr

        return LastPassResult(p.returncode, output)


class LastPassResult():
    """ Data structure that represents the result of a LastPass cli command """
    def __init__(self, return_code, output):
        self.return_code = return_code
        self.output = output
