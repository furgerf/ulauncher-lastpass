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
        cmd = "lpass show -G %s --json" % query

        result = self.lpass(cmd)

        if result.return_code != 0:
            return self.handle_errors(result.output)

        return self.parse_list_results(result.output)

    def parse_list_results(self, output):
        """ Parses the LastPass response """

        # Check if we get a json response. If yes, it means the LastPass cli
        # returned a single result and we have to treat it differently
        try:
            site_data = json.loads(output)
            item = site_data[0]
            return [{
                'id': item["id"],
                'name': item["name"],
                'folder': item["group"]
            }]
        except ValueError:
            pass

        # Process multiple matches
        items = []
        for line in output.splitlines():
            if "Multiple matches found" in line:
                continue

            # Split folder and site
            parts = line.split("/")

            folder = "/".join(parts[:len(parts) - 1])
            site = parts[len(parts) - 1]

            site_id_match = re.match(r".*\s\[id:\s(\d+)", site)

            if not site_id_match:
                logger.warn("Cannot parse site_id for string: %s", site)
                continue

            name_re = re.match(r"(.*)\[id:\s\d+]", site)
            items.append({
                'id': site_id_match.group(1),
                'name': name_re.group(1),
                'folder': folder,
            })

        return items

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

        if stdout:
            output = stdout
        else:
            output = stderr

        return LastPassResult(p.returncode, output)


class LastPassResult():
    """ Data structure that represents the result of a LastPass cli command """
    def __init__(self, return_code, output):
        self.return_code = return_code
        self.output = output
