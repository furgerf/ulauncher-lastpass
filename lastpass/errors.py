class LastPassError(Exception):
    def __init__(self, output):
        self.output = output


class CliNotInstalledException(Exception):
    pass
